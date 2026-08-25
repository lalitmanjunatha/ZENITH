"""Zenith Facial Recognition + People Directory Window.

Enroll people with photos (webcam burst or existing folders); when asked to
"run facial recognition", Zenith snaps the webcam, identifies everyone in
frame, and opens a dedicated Tkinter window showing:
  - top:  recognized person(s) — photo + full details
  - grid: EVERY person Zenith knows (photo thumbnails + details)
Unknowns are flagged ❓ with an Enroll button.

Engine ladder (first importable wins):
  1. face_recognition (dlib)      — best accuracy if installed
  2. OpenCV LBPH (opencv-contrib) — solid fallback
  3. OpenCV histogram signature   — guaranteed last resort

Everything stays 100% local. No HUD — this window opens only on request.
"""

import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
FACE_DIR = Path("data/faces")
CASCADE = None          # lazy-loaded Haar cascade
ENGINE_NAME = "histogram"


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS known_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            relationship TEXT,
            notes TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS person_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            image_path TEXT,
            encoding BLOB,
            FOREIGN KEY (person_id) REFERENCES known_people(id)
        );
        CREATE TABLE IF NOT EXISTS recognition_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            matched_person_id INTEGER,
            guessed_name TEXT,
            confidence REAL,
            snapshot_path TEXT
        );
        """
    )
    return conn


# ------------------------------------------------------------ engine setup --

def _load_engine():
    """Pick best available engine; returns (engine_name, encode_fn)."""
    global ENGINE_NAME
    try:
        import face_recognition as fr  # dlib-based
        ENGINE_NAME = "face_recognition(dlib)"

        def enc(pil_img):
            import numpy as np
            rgb = pil_img.convert("RGB")
            boxes = fr.face_locations(rgb)
            if not boxes:
                return None
            vec = fr.face_encodings(rgb, [boxes[0]])[0]
            return np.asarray(vec, dtype="float32").tobytes()
        return ENGINE_NAME, enc
    except Exception:
        pass

    try:
        import cv2
        import numpy as np
        if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            ENGINE_NAME = "opencv-lbph"
            recognizer_holder = {"rec": None}

            def enc_lbph(pil_img):
                gray = pil_img.convert("L")
                arr = np.array(gray)
                faces = _detect_faces(arr)
                if not faces:
                    return None
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                roi = cv2.resize(arr[y:y + h, x:x + w], (128, 128))
                rec = recognizer_holder["rec"]
                if rec is None:
                    rec = cv2.face.LBPHFaceRecognizer_create()
                    rec.train(np.zeros((1, 128, 128), dtype=np.uint8), np.array([0]))
                    recognizer_holder["rec"] = rec
                vec = rec.predict(roi)[1]
                return __import__("struct").pack("f", float(vec))
            return ENGINE_NAME, enc_lbph
    except Exception:
        pass

    # Guaranteed last resort: multi-size grayscale histogram signature
    import cv2
    ENGINE_NAME = "histogram"

    def enc_hist(pil_img):
        import numpy as np
        arr = np.array(pil_img.convert("L"))
        faces = _detect_faces(arr)
        if faces:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            arr = arr[max(0, y):y + h, max(0, x):x + w]
        import cv2 as _cv2
        r = _cv2.resize(arr, (96, 96))
        hist = _cv2.calcHist([r], [0], None, [64], [0, 256]).flatten()
        h2 = _cv2.calcHist([r], [0], None, [16], [0, 256]).flatten()
        import numpy as np
        return np.concatenate([hist / (hist.sum() + 1e-6),
                               h2 / (h2.sum() + 1e-6)]).astype("float32").tobytes()
    return ENGINE_NAME, enc_hist


def _detect_faces(gray_arr):
    """Haar-cascade detection on a grayscale numpy array."""
    global CASCADE
    try:
        import cv2

        if CASCADE is None:
            cpath = os.path.join(
                os.path.dirname(cv2.__file__), "data", "haarcascade_frontalface_default.xml")
            CASCADE = cv2.CascadeClassifier(cpath)
        faces = CASCADE.detectMultiScale(gray_arr, scaleFactor=1.15,
                                         minNeighbors=5, minSize=(60, 60))
        return [tuple(map(int, f)) for f in faces]
    except Exception as e:
        logger.debug(f"detect failed: {e}")
        return []


_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _load_engine()
    return _ENGINE


def _compare(e1: bytes, e2: bytes) -> float:
    """Return similarity in [0..1]."""
    try:
        import numpy as np
        a, b = np.frombuffer(e1, dtype="float32"), np.frombuffer(e2, dtype="float32")
        if ENGINE_NAME.startswith("face_recognition"):
            d = np.linalg.norm(a - b)
            return max(0.0, 1.0 - d / 1.2)
        na, nb = np.linalg.norm(a) + 1e-6, np.linalg.norm(b) + 1e-6
        return float(np.dot(a / na, b / nb))
    except Exception:
        return 0.0


# ------------------------------------------------------------- enrollment ---

def _save_face_crop(pil_img, person_id: int) -> str:
    import numpy as np
    arr = __import__("numpy").array(pil_img.convert("RGB"))
    gray = pil_img.convert("L")
    faces = _detect_faces(__import__("numpy").array(gray))
    pdir = FACE_DIR / str(person_id)
    pdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    if faces:
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        arr = arr[max(0, y):y + h, max(0, x):x + w]
    out = pdir / f"{stamp}.jpg"
    try:
        import cv2
        cv2.imwrite(str(out), arr[:, :, ::-1])
    except Exception:
        pil_img.save(out)
    return str(out)


@function_tool()
async def enroll_person(name: str, relationship: str = "", notes: str = "",
                        photo_folder: str = "") -> str:
    """ENROLL a person so Zenith recognizes them forever.

    Args:
        name: Person's name (unique)
        relationship: friend/brother/professor...
        notes: Anything to remember — shown in the people window
        photo_folder: Optional folder of their photos; if empty, a WEBCAM
                      capture burst runs now (look at the camera!)
    """
    try:
        engine, enc = _engine()
        conn = _db()
        cur = conn.execute(
            "INSERT INTO known_people (name,relationship,notes,created_at) VALUES (?,?,?,?)",
            (name.strip(), relationship.strip(), notes.strip(), datetime.now().isoformat()),
        )
        pid = cur.lastrowid

        added, frames = 0, []
        if photo_folder and os.path.isdir(photo_folder):
            from PIL import Image
            exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            for f in sorted(Path(photo_folder).rglob("*")):
                if f.suffix.lower() in exts:
                    try:
                        img = Image.open(f).convert("RGB")
                        if img.width > 1600:
                            img.thumbnail((1600, 1600))
                        frames.append(img)
                    except Exception:
                        continue
                    if len(frames) >= 30:
                        break
        else:
            frames = await asyncio_webcam_burst(count=8, delay=0.7)

        for img in frames:
            encb = enc(img)
            crop_path = _save_face_crop(img, pid)
            if encb:
                conn.execute(
                    "INSERT INTO person_photos (person_id,image_path,encoding) VALUES (?,?,?)",
                    (pid, crop_path, encb),
                )
                added += 1
        conn.commit()
        n = conn.execute("SELECT COUNT(*) c FROM person_photos WHERE person_id=?", (pid,)).fetchone()["c"]
        name_ = conn.execute("SELECT name FROM known_people WHERE id=?", (pid,)).fetchone()["name"]
        conn.close()
        if added == 0:
            return ("⚠️ Registered the person but no clear FACES were found in the "
                    f"photos ({n} stored anyway). Add clearer frontal photos via "
                    "add_person_photo for reliable recognition.")
        return (f"🧠 ENROLLED: {name_} ({relationship or 'contact'})\n"
                f"   📸 Faces learned: {added} | Engine: {engine}\n"
                f"   I will recognize them in facial recognition scans.")
    except Exception as e:
        return f"❌ Enrollment failed: {e}"


async def asyncio_webcam_burst(count: int = 8, delay: float = 0.7):
    """Capture N webcam frames asynchronously (best-effort)."""
    def _burst():
        import cv2
        from PIL import Image as PILImage
        cap = cv2.VideoCapture(0)
        out = []
        if not cap.isOpened():
            return out
        import time as _t
        _t.sleep(0.4)
        for _ in range(count):
            ok, frame = cap.read()
            if ok:
                out.append(PILImage.fromarray(frame[:, :, ::-1]))
            _t.sleep(delay)
        cap.release()
        return out

    import asyncio
    return await asyncio.to_thread(_burst)


@function_tool()
async def add_person_photo(name: str, image_path: str) -> str:
    """Add ONE more photo of an already-enrolled person (improves accuracy).

    Args:
        name: Enrolled person's name
        image_path: Path to a photo containing their face
    """
    try:
        engine, enc = _engine()
        conn = _db()
        row = conn.execute("SELECT id FROM known_people WHERE lower(name)=?",
                           (name.lower(),)).fetchone()
        if not row:
            conn.close()
            return f"❌ '{name}' not enrolled yet. Use enroll_person first."
        pid = row["id"]
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        encb = enc(img)
        crop = _save_face_crop(img, pid)
        if not encb:
            conn.close()
            return "❌ No face detected in that photo — try a clearer frontal shot."
        conn.execute("INSERT INTO person_photos (person_id,image_path,encoding) VALUES (?,?,?)",
                     (pid, crop, encb))
        n = conn.execute("SELECT COUNT(*) c FROM person_photos WHERE person_id=?", (pid,)).fetchone()["c"]
        conn.commit(); conn.close()
        return f"📸 Photo learned for {name}. Total reference photos: {n}."
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def list_known_people() -> str:
    """List everyone Zenith knows with photo counts."""
    conn = _db()
    rows = conn.execute(
        """SELECT k.id,k.name,k.relationship,k.notes,
                  (SELECT COUNT(*) FROM person_photos p WHERE p.person_id=k.id) photos
           FROM known_people k ORDER BY k.name""").fetchall()
    conn.close()
    if not rows:
        return ("👥 I know no one yet. Say: enroll_person(\"Name\", relationship, "
                "notes, photo_folder_or_empty_for_webcam).")
    out = f"👥 PEOPLE DATABASE — {len(rows)} known:\n"
    for r in rows:
        rel = f" ({r['relationship']})" if r["relationship"] else ""
        out += f"   • {r['name']}{rel} — {r['photos']} photo(s)"
        out += f" | {r['notes'][:60]}" if r["notes"] else ""
        out += "\n"
    return out


# ----------------------------------------------------------- recognition ----

def _identify(pil_img):
    """Match one image against all known encodings. Returns list of matches."""
    engine, enc = _engine()
    probe = enc(pil_img)
    if not probe:
        return []
    conn = _db()
    rows = conn.execute(
        """SELECT pp.encoding, k.id, k.name, k.relationship, k.notes
           FROM person_photos pp JOIN known_people k ON k.id=pp.person_id"""
    ).fetchall()
    conn.close()
    best = {}
    for r in rows:
        sim = _compare(probe, r["encoding"])
        if r["id"] not in best or sim > best[r["id"]][0]:
            best[r["id"]] = (sim, dict(r))
    matches = [(v[0], v[1]) for v in best.values() if v[0] >= 0.55]
    matches.sort(key=lambda x: -x[0])
    return matches


@function_tool()
async def run_facial_recognition() -> str:
    """RUN FACIAL RECOGNITION: webcam snap → identify everyone in frame →
    open the PEOPLE WINDOW showing recognized person(s) on top and your whole
    known-people gallery below. Also speaks a summary."""
    try:
        engine, enc = _engine()
        frames = await asyncio_webcam_burst(count=4, delay=0.6)
        if not frames:
            return "❌ Webcam unavailable — cannot run facial recognition."

        seen, unknown_faces = {}, 0
        for img in frames:
            import numpy as np
            gray_arr = np.array(img.convert("L"))
            faces = _detect_faces(gray_arr)
            if not faces:
                continue
            m = _identify(img)
            if m:
                for sim, info in m[:1]:
                    prev = seen.get(info["id"])
                    if not prev or sim > prev[0]:
                        seen[info["id"]] = (sim, info, img)
            else:
                unknown_faces += len(faces)

        # Log + snapshot best match crops
        conn = _db()
        named = []
        for pid, (sim, info, img) in seen.items():
            crop = _save_face_crop(img, pid)
            conn.execute(
                "INSERT INTO recognition_log (ts,matched_person_id,guessed_name,confidence,snapshot_path) VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), pid, info["name"], round(sim, 3), crop),
            )
            named.append((info["name"], info.get("relationship") or "", sim))
        conn.commit(); conn.close()

        open_people_window(highlight_ids=list(seen.keys()))

        if named:
            spoken = ", ".join(n for n, _, _ in named)
            extra = f" Plus {unknown_faces} unrecognized face(s)." if unknown_faces else ""
            return (f"👁️ FACIAL RECOGNITION COMPLETE (engine: {engine})\n"
                    f"✅ Recognized: {spoken}.{extra}\n"
                    "🪟 People window is now OPEN on screen with full details & gallery.")
        msg = ("❓ No known faces matched"
               + (f" — but {unknown_faces} unknown face(s) detected." if unknown_faces else "."))
        return (f"👁️ SCAN COMPLETE\n{msg}\n🪟 Window opened — use 'Enroll this face' "
                "to teach me a new person instantly.")
    except Exception as e:
        logger.exception("face scan failed")
        return f"❌ Recognition failed: {e}"


@function_tool()
async def remove_person(name: str) -> str:
    """Remove a person (and their photos) from the recognition database."""
    try:
        conn = _db()
        row = conn.execute("SELECT id FROM known_people WHERE lower(name)=?",
                           (name.lower(),)).fetchone()
        if not row:
            conn.close()
            return f"❌ '{name}' isn't in my database."
        conn.execute("DELETE FROM person_photos WHERE person_id=?", (row["id"],))
        conn.execute("DELETE FROM known_people WHERE id=?", (row["id"],))
        conn.commit(); conn.close()
        shutil.rmtree(FACE_DIR / str(row["id"]), ignore_errors=True)
        return f"🗑️ {name} removed from my memory banks."
    except Exception as e:
        return f"❌ Removal failed: {e}"


import shutil  # noqa: E402


# ------------------------------------------------------------- GUI window ---

_window_state = {"open": False}


def open_people_window(highlight_ids=None):
    """Open (or refresh) the People Directory Tkinter window on its own thread."""
    highlight_ids = set(highlight_ids or [])
    t = threading.Thread(target=_window_main, args=(highlight_ids,), daemon=True)
    t.start()


def _window_main(highlight_ids):
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
        from PIL import Image, ImageTk

        win = tk.Tk()
        win.title("ZENITH — Facial Database")
        win.geometry("980x720")
        win.configure(bg="#10141a")
        win.attributes("-topmost", True)

        header = tk.Label(win, text="👁️ ZENITH · PEOPLE DATABASE", bg="#10141a",
                          fg="#5fd7ff", font=("Segoe UI", 16, "bold"))
        header.pack(pady=(10, 2))

        status = tk.Label(win, text="", bg="#10141a", fg="#c8ffd4", font=("Segoe UI", 10))
        status.pack()

        body = tk.Frame(win, bg="#10141a")
        body.pack(fill="both", expand=True, padx=12, pady=8)

        canvas = tk.Canvas(body, bg="#10141a", highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        grid_frame = tk.Frame(canvas, bg="#10141a")
        grid_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _on_mousewheel(e):
            canvas.yview_scroll(-1 * (e.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        thumb_refs = []

        def render():
            for w in grid_frame.winfo_children():
                w.destroy()
            conn = _db()
            rows = conn.execute(
                """SELECT k.*,
                      (SELECT image_path FROM person_photos p WHERE p.person_id=k.id
                       ORDER BY id DESC LIMIT 1) AS photo
                   FROM known_people k ORDER BY k.name""").fetchall()
            conn.close()
            hi_row, norm_rows = [], []
            for r in rows:
                d = dict(r)
                (hi_row if d["id"] in highlight_ids else norm_rows).append(d)

            if hi_row:
                tk.Label(grid_frame, text="⭐ RECOGNIZED NOW", bg="#10141a",
                         fg="#ffd75f", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 4))
                wrap = tk.Frame(grid_frame, bg="#182430", bd=1, relief="solid")
                wrap.pack(fill="x", pady=(0, 12))
                inner = tk.Frame(wrap, bg="#182430")
                inner.pack(padx=14, pady=12)

            allrows = ([("HI", r) for r in hi_row] + [("NORM", r) for r in norm_rows])
            cols = 4
            for idx, (kind, d) in enumerate(allrows):
                card_bg = "#182430"
                card = tk.Frame(grid_frame if kind == "NORM" else inner,
                                bg=card_bg, padx=10, pady=10,
                                highlightthickness=1,
                                highlightbackground="#2a3b4d")
                if kind == "NORM":
                    r, cidx = divmod(idx - len(hi_row), cols)
                    card.grid(row=r, column=cidx, padx=8, pady=8, sticky="nsew")
                else:
                    card.pack(side="left", padx=14, pady=4)

                photo = None
                if d["photo"] and os.path.exists(d["photo"]):
                    try:
                        im = Image.open(d["photo"])
                        im.thumbnail((150, 150))
                        photo = ImageTk.PhotoImage(im)
                        thumb_refs.append(photo)
                        tk.Label(card, image=photo, bg=card_bg).pack()
                    except Exception:
                        pass
                if not photo:
                    tk.Label(card, text="🙂", bg=card_bg,
                             font=("Segoe UI Emoji", 40)).pack()
                nm = d["name"] + (" ⭐" if kind == "HI" else "")
                tk.Label(card, text=nm, bg=card_bg, fg="white",
                         font=("Segoe UI", 11, "bold")).pack(pady=(6, 0))
                if d["relationship"]:
                    tk.Label(card, text=d["relationship"], bg=card_bg,
                             fg="#9fb6c9").pack()
                if d["notes"]:
                    tk.Label(card, text=str(d["notes"])[:60], bg=card_bg,
                             fg="#7f95a8", wraplength=160).pack()

            count_txt = f"{len(rows)} people known"
            if hi_row:
                count_txt += f" · {len(hi_row)} just recognized ⭐"
            status.config(text=count_txt)

        def enroll_dialog():
            top = tk.Toplevel(win)
            top.title("Enroll New Person")
            top.configure(bg="#10141a")
            top.attributes("-topmost", True)
            labels = ["Name*", "Relationship", "Notes"]
            entries = {}
            for i, lab in enumerate(labels):
                tk.Label(top, text=lab, bg="#10141a", fg="white").grid(row=i, column=0, sticky="e", padx=8, pady=6)
                e = tk.Entry(top, width=34)
                e.grid(row=i, column=1, padx=8, pady=6)
                entries[lab] = e
            res_box = tk.Label(top, text="", bg="#10141a", fg="#c8ffd4", wraplength=360)
            res_box.grid(row=3, column=0, columnspan=2)

            def do_enroll(use_cam=True):
                nm = entries["Name*"].get().strip()
                if not nm:
                    res_box.config(text="Name required.", fg="#ff9a9a"); return
                folder = "" if use_cam else __import__(
                    "tkinter.filedialog", fromlist=["askdirectory"]).askdirectory(title="Pick their photo folder")
                res_box.config(text="Working… look at camera!" if use_cam else "Learning photos…")

                def work():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    r = loop.run_until_complete(enroll_person(
                        name=nm,
                        relationship=entries["Relationship"].get(),
                        notes=entries["Notes"].get(),
                        photo_folder=folder or ""))
                    top.after(0, lambda: (res_box.config(text=r.replace("❌", "").replace("⚠️", "")[:300]),
                                          render()))
                threading.Thread(target=work, daemon=True).start()

            btns = tk.Frame(top, bg="#10141a"); btns.grid(row=4, column=0, columnspan=2, pady=10)
            tk.Button(btns, text="📸 Capture via webcam", command=lambda: do_enroll(True),
                      bg="#1f6feb", fg="white", padx=12).pack(side="left", padx=6)
            tk.Button(btns, text="📁 Pick photo folder", command=lambda: do_enroll(False),
                      bg="#238636", fg="white", padx=12).pack(side="left", padx=6)

        btnbar = tk.Frame(win, bg="#10141a")
        btnbar.pack(pady=(0, 12))
        tk.Button(btnbar, text="🔄 Refresh", command=render, bg="#21262d",
                  fg="white", padx=14).pack(side="left", padx=6)
        tk.Button(btnbar, text="➕ Add Person", command=enroll_dialog, bg="#1f6feb",
                  fg="white", padx=14).pack(side="left", padx=6)

        async_close = tk.Button(btnbar, text="✖ Close", command=win.destroy,
                                bg="#da3633", fg="white", padx=14)
        async_close.pack(side="left", padx=6)

        render()
        _window_state["open"] = True
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), _window_state.update({"open": False})))
        win.mainloop()
        _window_state["open"] = False
    except Exception as e:
        logger.warning(f"people window failed: {e}")
        _window_state["open"] = False


@function_tool()
async def open_people_directory() -> str:
    """Open the PEOPLE DIRECTORY window anytime — every person Zenith knows,
    with their photo and details. ('Show me everyone you know.')"""
    try:
        conn = _db()
        n = conn.execute("SELECT COUNT(*) c FROM known_people").fetchone()["c"]
        conn.close()
        open_people_window()
        if n == 0:
            return ("🪟 Window opened — it's empty because nobody's enrolled yet. "
                    "Use ➕ Add Person inside, or enroll_person.")
        return f"🪟 People directory OPEN — {n} known face(s) on display."
    except Exception as e:
        return f"❌ Could not open window: {e}"
