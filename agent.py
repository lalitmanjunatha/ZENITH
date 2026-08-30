# =========================
# ENV + CORE IMPORTS
# =========================
from dotenv import load_dotenv
import asyncio
import os
import sys
import time
import json
import socket
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# =========================
# LIVEKIT IMPORTS
# =========================
from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import google as livekit_google

# Gemini realtime (network-safe)
network_available = False
try:
    socket.create_connection(("8.8.8.8", 53), timeout=3)
    from livekit.plugins.google.beta.realtime import RealtimeModel
    network_available = True
except Exception:
    print("⚠️ Network issue → Offline fallback mode")

# =========================
# PROMPTS
# =========================
from prompts import (
    AGENT_INSTRUCTION,
    SESSION_INSTRUCTION,
    AGENT_INSTRUCTION_FOR_TOOLS,
    MEMORY_AND_SELF_LEARNING_INSTRUCTION,
    SCHEDULER_AND_GOALS_INSTRUCTION,
    TELEPHONY_INSTRUCTION,
    SIH_INSTRUCTION,
    FUTURISTIC_INSTRUCTION,
    NEW_FEATURES_INSTRUCTION,
    BATCH3_INSTRUCTION,
    JARVIS_CORE_INSTRUCTION,
    USEFUL50_INSTRUCTION,
)
# =========================
# ML/NLP/LLM MODULES
# =========================
from zenith_brain import ZenithBrain

# =========================
# TOOLS (ALL)
# =========================
from Tools.manage_windows import manage_window, list_windows
from Tools.search_web import search_web
from Tools.send_whatsapp_message import send_whatsapp_message
from Tools.system_power_action import system_power_action
from Tools.type_user_message_auto import type_user_message_auto
from Tools.write_in_notepad import write_in_notepad
from Tools.desktop_control import desktop_control
from Tools.scroll_content import scroll_content
from Tools.code_handler import fix_code_error
from Tools.file_searching import universal_file_opener
from Tools.press_key import press_key, use_smart_clipboard
from Tools.open_app import open_app
from Tools.scan_system_for_viruses import scan_system_for_viruses
from Tools.time_volume_bright import (
    control_screen_brightness,
    control_system_volume,
    get_time_info,
    get_weather,
    get_system_info_deep,
)
from Tools.multi_task import execute_multi_task
from Tools.generate_ai_image import generate_ai_image
from Tools.code_generator import generate_and_type_code, run_file_in_vscode
from Tools.news_provider import get_top_news
from Tools.youtube_videos import play_media
from Tools.reminder import set_reminder, view_reminders, cancel_reminder
from Tools.screen_short import screen_short
from Tools.pdf_reader import process_document_query
from Tools.send_media_whatsapp import send_media_to_whatsapp
from Tools.excel_data_entery  import create_excel_file,save_excel_changes,delete_all_data,move_left,move_up,enter_data_quick,enter_multiple_data_quick,move_down,move_right,delete_current_cell,go_to_cell,toggle_text_bold,select_row_or_column,sort_excel_data,excel_clipboard_action,calculate_sum
from Tools.word_to_pdf  import word_to_pdf,image_to_pdf,excel_to_pdf,ppt_to_pdf,convert_image_format,test_converters
from Tools.create_folder  import create_here
from Tools.create_folder import create_here
from Tools.read_screen_text import read_screen_text
from Tools.camera_analysis import camera_analysis
from Tools.screen_analyzer import analyze_screen
from Tools.image_analysis import analyze_local_image
from Tools.click_on_element import click_on_element, get_clickable_elements, click_at_position, double_click_at_position
from Tools.window_focus import focus_window, list_windows_with_details, minimize_all_windows, restore_all_windows
from Tools.sih_project_manager import (  # SIH COMMAND CENTER
    sih_command_center,
    create_project,
    list_projects,
    select_project,
    get_project_details,
    get_project_stats,
    add_team_member,
    add_idea,
    add_research,
    add_architecture,
    add_feature,
    add_risk,
    add_evidence,
    add_decision,
)
from Tools.sih_tools import (  # SIH SUBSYSTEMS
    analyze_problem_statement,
    generate_ideas,
    kill_idea,
    compare_ideas,
    score_project,
    research_topic,
    find_existing_solutions,
    find_datasets,
    generate_architecture as sih_generate_architecture,
    plan_mvp,
    start_hackathon_mode,
    start_judge_mode,
    answer_judge_question,
    start_mock_jury,
    run_final_audit,
)
from Tools.laptop_health import get_laptop_health, predict_storage, run_health_snapshot
from Tools.file_janitor import scan_cleanup_candidates, execute_cleanup  # FILE JANITOR
from Tools.dream_mode import dream_now, dream_status, last_dream_summary  # DREAM MODE

# ============ NEW BATCH: CONTEXT / COMMS / EXPLAINER / FUN / DOCTOR ============
from Tools.context_engine import (
    wifi_profile, set_wifi_profile, app_usage_report,
    start_focus_session, end_focus_session,
)
from Tools.comms_hub import (
    unread_digest, read_important_emails, add_triage_rule, list_triage_rules,
    draft_whatsapp_reply, schedule_message, list_scheduled_messages,
    cancel_scheduled_message, add_birthday, check_birthdays, draft_birthday_greeting,
)
from Tools.system_explainer import explain_process, top_processes
from Tools.fun_personality import (
    set_persona, current_persona_info, tell_story, roast_me,
    trivia_start, trivia_answer,
)
from Tools.tool_doctor import (
    tool_health_dashboard, report_tool_issue, resolve_tool_issue, suggest_repairs,
)

# ============ BATCH 3: MONITOR / RENAMER / RITUAL / AUDIO / VIDEO / VDESK ============
from Tools.smart_monitors import (
    start_screen_monitor, stop_screen_monitor, screen_monitor_status,
)
from Tools.file_renamer import suggest_rename, apply_rename, scan_rename_candidates
from Tools.shutdown_ritual import shutdown_preview, execute_shutdown, cancel_shutdown
from Tools.audio_intel import (
    what_song_now, present_start, present_next, present_previous,
    present_goto, present_end, present_black_screen,
)
from Tools.web_video import summarize_youtube
from Tools.desktop_conductor import (
    vdesk_switch, vdesk_previous, vdesk_next, vdesk_new,
    vdesk_close_current, move_window_to_vdesk,
)
from Tools.guest_mode import enable_guest_mode, disable_guest_mode, guest_status
from Tools.time_capsule import create_time_capsule, check_time_capsules, delete_time_capsule

# ============ JARVIS CORE + AUTONOMY (Phases A/B/C/D/F/G) ============
from Tools.boot_sequence import build_boot_text
from Tools.damage_report import damage_report
from Tools.protocols import (
    run_protocol, create_protocol, list_protocols, delete_protocol,
)
from Tools.autonomy import (
    set_autonomy, full_stop, resume_autonomy, autonomy_status,
    undo_last_actions, decide_and_act, run_daily_digest,
)
from Tools.missions import catch_me_up, daily_threat_board, cue_music, power_check
from Tools.face_recognition import (
    enroll_person, add_person_photo, list_known_people, remove_person,
    run_facial_recognition, open_people_directory,
)
from Tools.call_butler import (
    butler_loop, set_session as butler_set_session, note_transcript,
    connect_me_to_caller, let_ai_handle_call, decline_this_call, recent_calls,
)
from Tools.whatsapp_x import (
    send_whatsapp_smart, confirm_contact, read_whatsapp_chat,
    reply_whatsapp_last, whatsapp_call, add_whatsapp_alias, list_whatsapp_contacts,
)

# ============ USEFUL-50 BATCH (F1,F2,F7,F21,F22,F24,F25,F26,F27,F31,F32,F36,F38,F46,F48) ====
from Tools.pdf_studio import (
    pdf_page_info, pdf_extract_pages, pdf_delete_pages,
    pdf_reorder_pages, pdf_merge, pdf_watermark,
)
from Tools.text_tools import fix_grammar, rewrite_tone
from Tools.network_ops import (
    list_wifi_profiles, wifi_passwords, internet_diagnostics, reset_network,
)
from Tools.battery_coach import battery_coach
from Tools.file_radar import scan_old_files, archive_old_files
from Tools.update_watchdog import (
    check_updates, install_app_updates, enable_update_monthly_watch,
)
from Tools.web_reader import save_article_as_pdf
from Tools.life_memory import (
    remember_item_location, find_item, list_tracked_items,
    add_inventory_item, packing_checklist, list_inventory,
)
from Tools.media_tools import video_to_mp3, compress_images
from Tools.session_handoff import (
    save_session_handoff, resume_session, relaunch_handoff_apps,
)
from Tools.skill_installer import install_skill, list_installed_skills
from Tools.laptop_watcher import (
    laptop_status, watch_laptop, stop_laptop_watch, laptop_watch_status,
    set_session as watcher_set_session,
)
from Tools.device_bridge import start_bridge_server
from Tools.phone_control import (
    phone_battery, phone_flashlight, phone_vibrate,
    phone_notify, phone_status,
)
from Tools.spotify import open_spotify,spotify_next,spotify_previous,spotify_play_song,spotify_play_liked,spotify_pause
from Tools.ml_tools import (
    train_classification_model,
    train_regression_model,
    cluster_data,
    detect_anomalies,
    analyze_data,
)
from Tools.nlp_tools import (
    analyze_sentiment,
    extract_entities,
    summarize_text,
    detect_language,
    preprocess_text,
)
from Tools.data_tools import (
    index_my_files,
    search_my_files,
    get_knowledge_stats,
    analyze_dataset,
)
from Tools.knowledge_search import (
    search_knowledge,
    index_files,
    ask_about_my_data,
)
from Tools.memory_tools import (
    store_memory,
    recall_memory,
    what_do_you_remember,
    train_from_conversations,
    get_memory_stats,
)
from Tools.self_edit import modify_source_file, read_source_file
from Tools.privacy_tools import (
    pause_memory,
    resume_memory,
    do_not_remember_that,
    memory_status,
)
from Tools.planner import execute_goal

# =========================
# MAIN AGENT
# =========================
class UltimateAdvancedZenith(Agent):
    def __init__(self):
        self._reminders: Dict[str, Dict[str, Any]] = {}
        self._reminder_task: Optional[asyncio.Task] = None
        self._session: Optional[AgentSession] = None
        self._reminder_counter = 0

        tools = [
            search_web,
            get_time_info,
            open_app,
            get_system_info_deep,
            get_weather,
            manage_window,
            list_windows,
            focus_window,
            list_windows_with_details,
            minimize_all_windows,
            restore_all_windows,
            play_media,
            press_key,
            write_in_notepad,
            desktop_control,
            scroll_content,
            send_whatsapp_message,
            use_smart_clipboard,
            universal_file_opener,
            system_power_action,
            get_top_news,
            execute_multi_task,
            generate_and_type_code,
            run_file_in_vscode,
            screen_short,
            click_on_element,
            get_clickable_elements,
            click_at_position,
            double_click_at_position,
            type_user_message_auto,
            scan_system_for_viruses,
            control_system_volume,
            control_screen_brightness,
            generate_ai_image,
            fix_code_error,
            set_reminder,
            view_reminders,
            cancel_reminder,
            process_document_query,
            send_media_to_whatsapp,
            create_excel_file,
                save_excel_changes,
                delete_all_data,
                move_left,
                move_up,
                enter_data_quick,
                enter_multiple_data_quick,
                move_down,
                move_right,
                delete_current_cell,
                go_to_cell,
                toggle_text_bold,
                select_row_or_column,
                sort_excel_data,
                excel_clipboard_action,
                calculate_sum,
                word_to_pdf,
                image_to_pdf,
                excel_to_pdf,
                ppt_to_pdf,
                convert_image_format,
                test_converters,
                create_here,
                read_screen_text,
                camera_analysis,
                analyze_screen,
                analyze_local_image,
                open_spotify,
                spotify_next,
                spotify_previous,
                spotify_play_song,
                spotify_play_liked,
                spotify_pause,
                train_classification_model,
                train_regression_model,
                cluster_data,
                detect_anomalies,
                analyze_data,
                analyze_sentiment,
                extract_entities,
                summarize_text,
                detect_language,
                preprocess_text,
                index_my_files,
                search_my_files,
                get_knowledge_stats,
                analyze_dataset,
                search_knowledge,
                index_files,
                ask_about_my_data,
                store_memory,
                recall_memory,
                what_do_you_remember,
                train_from_conversations,
                get_memory_stats,
                modify_source_file,
                read_source_file,
                pause_memory,
                resume_memory,
                do_not_remember_that,
                memory_status,
                execute_goal,

                # ============ SIH COMMAND CENTER ============
                sih_command_center,
                create_project,
                list_projects,
                select_project,
                get_project_details,
                get_project_stats,
                add_team_member,
                add_idea,
                add_research,
                add_architecture,
                add_feature,
                add_risk,
                add_evidence,
                add_decision,

                # ============ SIH SUBSYSTEMS ============
                analyze_problem_statement,
                generate_ideas,
                kill_idea,
                compare_ideas,
                score_project,
                research_topic,
                find_existing_solutions,
                find_datasets,
                sih_generate_architecture,
                plan_mvp,
                start_hackathon_mode,
                start_judge_mode,
                answer_judge_question,
                start_mock_jury,
                run_final_audit,

                # ============ FUTURISTIC: LAPTOP HEALTH ORACLE ============
                get_laptop_health,
                predict_storage,
                run_health_snapshot,

                # ============ FUTURISTIC: FILE JANITOR ============
                scan_cleanup_candidates,
                execute_cleanup,

                # ============ FUTURISTIC: DREAM MODE ============
                dream_now,
                dream_status,
                last_dream_summary,

                # ============ CONTEXT ENGINE (6, 10, 12) ============
                wifi_profile,
                set_wifi_profile,
                app_usage_report,
                start_focus_session,
                end_focus_session,

                # ============ COMMS HUB (73-77, 80) ============
                unread_digest,
                read_important_emails,
                add_triage_rule,
                list_triage_rules,
                draft_whatsapp_reply,
                schedule_message,
                list_scheduled_messages,
                cancel_scheduled_message,
                add_birthday,
                check_birthdays,
                draft_birthday_greeting,

                # ============ SYSTEM EXPLAINER (82) ============
                explain_process,
                top_processes,

                # ============ FUN & PERSONALITY (101, 105) ============
                set_persona,
                current_persona_info,
                tell_story,
                roast_me,
                trivia_start,
                trivia_answer,

                # ============ TOOL DOCTOR (106, 107) ============
                tool_health_dashboard,
                report_tool_issue,
                resolve_tool_issue,
                suggest_repairs,

                # ============ BATCH 3 (6,7,10,39,42,74,91,103,106) ============
                start_screen_monitor,
                stop_screen_monitor,
                screen_monitor_status,
                suggest_rename,
                apply_rename,
                scan_rename_candidates,
                shutdown_preview,
                execute_shutdown,
                cancel_shutdown,
                what_song_now,
                present_start,
                present_next,
                present_previous,
                present_goto,
                present_end,
                present_black_screen,
                summarize_youtube,
                vdesk_switch,
                vdesk_previous,
                vdesk_next,
                vdesk_new,
                vdesk_close_current,
                move_window_to_vdesk,
                enable_guest_mode,
                disable_guest_mode,
                guest_status,
                create_time_capsule,
                check_time_capsules,
                delete_time_capsule,

                # ============ JARVIS CORE (A) ============
                damage_report,
                catch_me_up,
                daily_threat_board,
                cue_music,
                power_check,

                # ============ PROTOCOLS (B) ============
                run_protocol,
                create_protocol,
                list_protocols,
                delete_protocol,

                # ============ AUTONOMY CORE (F) ============
                set_autonomy,
                full_stop,
                resume_autonomy,
                autonomy_status,
                undo_last_actions,
                decide_and_act,
                run_daily_digest,

                # ============ FACE RECOGNITION (D) ============
                enroll_person,
                add_person_photo,
                list_known_people,
                remove_person,
                run_facial_recognition,
                open_people_directory,

                # ============ CALL BUTLER (G) ============
                connect_me_to_caller,
                let_ai_handle_call,
                decline_this_call,
                recent_calls,

                # ============ WHATSAPP X (smart contacts/calls) ============
                send_whatsapp_smart,
                confirm_contact,
                read_whatsapp_chat,
                reply_whatsapp_last,
                whatsapp_call,
                add_whatsapp_alias,
                list_whatsapp_contacts,

                # ============ PDF STUDIO (F1,F2) ============
                pdf_page_info,
                pdf_extract_pages,
                pdf_delete_pages,
                pdf_reorder_pages,
                pdf_merge,
                pdf_watermark,

                # ============ TEXT TOOLS (F7) ============
                fix_grammar,
                rewrite_tone,

                # ============ NETWORK OPS (F21,F22) ============
                list_wifi_profiles,
                wifi_passwords,
                internet_diagnostics,
                reset_network,

                # ============ BATTERY COACH (F24) ============
                battery_coach,

                # ============ FILE RADAR (F25) ============
                scan_old_files,
                archive_old_files,

                # ============ UPDATE WATCHDOG (F26) ============
                check_updates,
                install_app_updates,
                enable_update_monthly_watch,

                # ============ WEB READER (F27) ============
                save_article_as_pdf,

                # ============ LIFE MEMORY (F31,F32) ============
                remember_item_location,
                find_item,
                list_tracked_items,
                add_inventory_item,
                packing_checklist,
                list_inventory,

                # ============ MEDIA TOOLS (F36,F38) ============
                video_to_mp3,
                compress_images,

                # ============ SESSION HANDOFF (F46) ============
                save_session_handoff,
                resume_session,
                relaunch_handoff_apps,

                # ============ SKILL INSTALLER (F48) ============
                install_skill,
                list_installed_skills,

                # ============ CROSS-DEVICE (mobile bridge + laptop watcher) ====
                laptop_status,
                watch_laptop,
                stop_laptop_watch,
                laptop_watch_status,

                # ============ PHONE CONTROL (laptop → phone) ============
                phone_battery,
                phone_flashlight,
                phone_vibrate,
                phone_notify,
                phone_status,
        ]

        # ── SAFETY NET: dedupe by registered tool name (prevents LiveKit
        #    "duplicate function name" crash if a name ever appears twice) ──
        seen_names = set()
        deduped = []
        for t in tools:
            try:
                tname = getattr(getattr(t, "info", None), "name", None) or getattr(t, "__name__", repr(t))
            except Exception:
                tname = repr(t)
            if tname in seen_names:
                print(f"⚠️ Duplicate tool skipped: {tname}")
                continue
            seen_names.add(tname)
            deduped.append(t)
        tools = deduped

        self.brain = ZenithBrain()
        self.brain.initialize()

        self.memory: Optional["MemoryManager"] = None
        try:
            from memory_manager import MemoryManager
            self.memory = MemoryManager()
        except Exception as e:
            print(f"⚠️ Memory manager unavailable: {e}")
            self.memory = None

        self.scheduler: Optional["ReminderScheduler"] = None
        try:
            from scheduler import ReminderScheduler
            self.scheduler = ReminderScheduler()
        except Exception as e:
            print(f"⚠️ Scheduler manager unavailable: {e}")
            self.scheduler = None

        self._scheduler_task: Optional[asyncio.Task] = None

        super().__init__(
            instructions=self._build_instructions(),
            tools=tools,
            llm=self._init_llm(),
        )

        print(f"✅ Zenith initialized with {len(tools)} tools")

    def _init_llm(self):
        if network_available:
            from google.genai import types as gemini_types
            return RealtimeModel(
                model="gemini-2.0-flash-live-001",
                voice="Kore",
                temperature=0.7,
                language="en-US",
                max_output_tokens=1024,
                input_audio_transcription=gemini_types.AudioTranscriptionConfig(),
                output_audio_transcription=gemini_types.AudioTranscriptionConfig(),
            )
        return None

    def _build_instructions(self):
        memory_block = ""
        if self.memory:
            try:
                facts = self.memory.all_facts()
                if facts:
                    lines = " ; ".join(f.get("content", "") for f in facts)
                    memory_block = (
                        "## THINGS YOU ALREADY REMEMBER ABOUT THIS USER (use these; do not ask again):\n"
                        f"{lines}\n"
                    )
            except Exception:
                pass
        # Persona pack + guest-mode restrictions (live state)
        persona_block = ""
        try:
            from Tools.fun_personality import get_persona_instruction
            persona_block = "\n" + get_persona_instruction()
        except Exception:
            pass
        guest_block = ""
        try:
            from Tools.guest_mode import guest_instruction_block
            guest_block = guest_instruction_block()
            if guest_block:
                # Guests never get the owner's memory block
                memory_block = ""
        except Exception:
            pass
        return "\n".join([
            memory_block,
            AGENT_INSTRUCTION,
            AGENT_INSTRUCTION_FOR_TOOLS,
            MEMORY_AND_SELF_LEARNING_INSTRUCTION,
            SCHEDULER_AND_GOALS_INSTRUCTION,
            SIH_INSTRUCTION,
            FUTURISTIC_INSTRUCTION,
            NEW_FEATURES_INSTRUCTION,
            BATCH3_INSTRUCTION,
            JARVIS_CORE_INSTRUCTION,
            USEFUL50_INSTRUCTION,
            "You have access to ALL system, voice, automation and reminder tools.",
            "Use tools aggressively when required.",
            "You are ML/NLP/LLM-powered. You can train models, analyze data, process text, and search your personal knowledge base.",
            "When asked about data analysis, use the ML tools (train_classification_model, train_regression_model, cluster_data, detect_anomalies, analyze_data).",
            "When asked about text analysis, use the NLP tools (analyze_sentiment, extract_entities, summarize_text, detect_language, preprocess_text).",
            "When asked about your personal files or knowledge, use the knowledge tools (search_knowledge, index_files, ask_about_my_data, index_my_files, search_my_files, get_knowledge_stats).",
            "Always classify the user's intent as ML, NLP, RAG, file_open, or general LLM, and route to the appropriate tool.",
            "If the user asks about personal data (Aadhaar, PAN, documents), search your indexed files by content and tell them what you found.",
            "If the user asks to open a file, find it by content and open it using the file system.",
            "AUTO-COMMAND MATCHING: When the user's message relates to any tool's functionality, silently auto-execute the matching tool without announcing the tool name or internal module. Simply act and report the result naturally. Do NOT ask 'Do you want me to do that?' for tool-related commands — just execute them.",
        ])

    # =========================
    # REMINDER SYSTEM
    # =========================
    def set_session(self, session: AgentSession):
        self._session = session
        print("🔔 Session linked for reminders")

    def add_reminder(self, text: str, time_: datetime):
        rid = f"rem_{self._reminder_counter}"
        self._reminder_counter += 1

        self._reminders[rid] = {
            "text": text,
            "time": time_,
        }

        if not self._reminder_task or self._reminder_task.done():
            self._reminder_task = asyncio.create_task(self._monitor_reminders())

        return rid

    async def _monitor_reminders(self):
        print("⏰ Reminder monitor running")
        while self._reminders:
            now = datetime.now()
            triggered = []

            for rid, data in self._reminders.items():
                if now >= data["time"]:
                    await self._trigger_reminder(data["text"])
                    triggered.append(rid)

            for rid in triggered:
                self._reminders.pop(rid, None)

            await asyncio.sleep(5)

    async def _trigger_reminder(self, text: str):
        if self._session:
            await self._session.generate_reply(
                instructions=f"Reminder: {text}"
            )
            print(f"🔔 Reminder sent → {text}")

# =========================
# ENTRYPOINT
# =========================
async def entrypoint(ctx: agents.JobContext):
    print("🚀 Starting Zenith...")

    agent = UltimateAdvancedZenith()
    session = AgentSession()

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            video_enabled=False,
        ),
    )

    agent.set_session(session)

    # Persist every exchange into long-term memory.
    if agent.memory:
        def on_conversation_item(evt):
            try:
                item = evt.item
                role = getattr(item, "role", None)
                text = getattr(item, "text", "")
                role_name = getattr(role, "value", role) if role is not None else None
                if role in ("user", "assistant") or role_name in ("user", "assistant"):
                    agent.memory.record_message(role_name or role, text)
            except Exception as e:
                print(f"⚠️ memory capture error: {e}")

        session.on("conversation_item_added", on_conversation_item)
        # Call-butter transcript capture while screening AI-handled calls
        try:
            from Tools.call_butler import note_transcript as _cb_note

            def on_item_for_butler(evt):
                try:
                    it = evt.item
                    r = getattr(it, "role", None)
                    rn = getattr(r, "value", r) if r is not None else None
                    _cb_note(rn or str(r), getattr(it, "text", ""))
                except Exception:
                    pass
            session.on("conversation_item_added", on_item_for_butler)
        except Exception:
            pass

    await ctx.connect()
    call_ctx = _detect_call_context(ctx.room)
    instructions = SESSION_INSTRUCTION
    if call_ctx:
        instructions = SESSION_INSTRUCTION + "\n\n" + TELEPHONY_INSTRUCTION + "\n" + call_ctx
        print(f"📞 Call-aware session: {call_ctx.decode('utf-8') if isinstance(call_ctx, bytes) else call_ctx}")

    asyncio.create_task(_auto_index_files(agent))
    asyncio.create_task(_scheduler_loop(agent, session))
    asyncio.create_task(_morning_brief(agent, session))
    asyncio.create_task(_dream_loop(agent))
    asyncio.create_task(_context_loops())
    asyncio.create_task(_jarvis_loops(session))

    # Cross-device bridge server (phone connects here)
    asyncio.create_task(start_bridge_server(agent, session))

    # Cloud link daemon (laptop dials OUT to render.com; no port forwarding)
    asyncio.create_task(_spawn_cloud_client())

    # JARVIS cinematic boot (voice) — falls back to standard greeting
    try:
        from Tools.boot_sequence import run_boot
        if not await run_boot(session):
            await session.generate_reply(instructions=instructions)
    except Exception:
        await session.generate_reply(instructions=instructions)

    print("🔥 Zenith is LIVE & READY")
    _start_watchdog(session)

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        print("🛑 Zenith stopped")
        try:
            await asyncio.to_thread(
                _consolidate_memory, agent
            )
        except Exception as e:
            print(f"⚠️ Memory consolidation failed: {e}")


async def _dream_loop(agent):
    """Dream Mode watchdog: every minute, dream if the user has been idle long enough."""
    print("🌙 Dream Mode watchdog on")
    from Tools.dream_mode import maybe_dream
    while True:
        try:
            await maybe_dream(agent)
        except Exception as e:
            print(f"⚠️ Dream tick error: {e}")
        await asyncio.sleep(60)


async def _context_loops():
    """Context Engine loops: app-usage sampler, focus-mode enforcer,
    and the scheduled-message dispatcher."""
    import contextlib

    from Tools.context_engine import focus_loop, usage_sampler_loop
    from Tools.comms_hub import dispatch_due_messages

    async def dispatcher_loop():
        while True:
            try:
                await dispatch_due_messages()
            except Exception as e:
                print(f"⚠️ Dispatcher error: {e}")
            await asyncio.sleep(30)

    print("🧭 Context engine loops on (sampler / focus / dispatcher)")
    with contextlib.suppress(Exception):
        await asyncio.gather(usage_sampler_loop(), focus_loop(), dispatcher_loop())


# ===================== JARVIS LOOPS + WATCHDOG =============================

_last_activity = {"ts": 0.0}
_watchdog_started = False


def _touch_activity():
    _last_activity["ts"] = __import__("time").time()


async def _jarvis_loops(session):
    """Call Butler watcher + Autonomy initiative engine + wake-word daemon + laptop watcher."""
    from Tools.call_butler import butler_loop, set_session as cb_set_session
    from Tools.autonomy import initiative_loop
    from Tools.wake_word_daemon import start_daemon
    from Tools.laptop_watcher import set_session as lw_set_session

    cb_set_session(session)
    lw_set_session(session)  # laptop watcher can announce transitions vocally
    mode = start_daemon()
    print(f"🎧 Wake-word daemon: {mode} (say 'Zenith' anytime)")

    async def initiative(session_):
        await initiative_loop(None)   # session passed via holder below

    # pass live session into initiative via closure refresh
    async def initiative_with_session():
        from Tools.autonomy import initiative_tick
        while True:
            try:
                await initiative_tick(_session_holder.get("session"))
            except Exception:
                pass
            await asyncio.sleep(180)

    global _session_holder
    _session_holder["session"] = session

    await asyncio.gather(
        butler_loop(session),
        initiative_with_session(),
    )


_session_holder = {}


def _start_watchdog(session):
    """Cures: (1) idle>90s stall, (2) unresponsive-after-commands.
    Strategy: activity heartbeat + rescue-flag check; on failure in console
    mode → auto-relaunch a fresh console (state persists on disk)."""
    global _watchdog_started
    if _watchdog_started:
        return
    _watchdog_started = True

    def _bump(*_):
        _touch_activity()
    try:
        session.on("conversation_item_added", _bump)
        session.on("user_input_transcribed", _bump)
    except Exception:
        pass
    _touch_activity()

    async def watchdog():
        import time as _t
        import os as _os
        console_mode = "console" in sys.argv
        while True:
            await asyncio.sleep(15)
            try:
                from Tools.wake_word_daemon import rescue_requested, clear_rescue, \
                    launch_agent_console
                idle = _t.time() - _last_activity["ts"]

                if rescue_requested():
                    print("🎧 Wake word detected — reviving Zenith…")
                    clear_rescue()
                    if console_mode:
                        launch_agent_console()
                        _os._exit(0)
                    continue

                # Stall cure #1: silent >90s → gentle self-ping proves life
                if 90 < idle <= 300:
                    try:
                        await asyncio.wait_for(
                            session.generate_reply(
                                instructions='Say exactly: "Still here, sir. Systems green."'),
                            timeout=25)
                        _touch_activity()
                    except Exception:
                        print("⚠️ Watchdog: session failed self-ping — recovering…")
                        _recover(console_mode)
                        return
                # Stall cure #2: long-dead (>300s silence)
                elif idle > 300 and console_mode:
                    print("⚠️ Watchdog: prolonged silence — refreshing session…")
                    _recover(console_mode)
                    return
            except Exception as e:
                logger.debug(f"watchdog tick: {e}")

    def _recover(console_mode: bool):
        from Tools.wake_word_daemon import launch_agent_console
        print("🔁 Watchdog recovery: spawning fresh Zenith…")
        if console_mode:
            launch_agent_console()
            _os = __import__("os")
            _os._exit(0)
        # worker mode: leave process alive (LiveKit supervisor handles jobs)

    asyncio.create_task(watchdog())
    print("🛡️ Watchdog armed (idle-stall & dead-session auto-recovery)")


def _detect_call_context(room) -> str:
    """If this room is a Zenith Phone call, return a context line for the model."""
    try:
        parts = getattr(room, "remote_participants", {}) or {}
        for p in parts.values():
            md = (getattr(p, "metadata", "") or "").strip()
            if not md or md.startswith("{"):
                if not md:
                    continue
                try:
                    d = json.loads(md)
                    if d.get("zenith_call"):
                        caller = d.get("caller") or ""
                        direction = d.get("direction") or "inbound"
                        line = f"CALL CONTEXT: caller='{caller}' direction={direction}"
                        return line
                except Exception:
                    continue
        return ""
    except Exception:
        return ""


async def _scheduler_loop(agent, session):
    if not (agent and agent.scheduler):
        return
    agent.scheduler.set_notifier(
        lambda msg: asyncio.create_task(_speak(agent, session, msg))
    )
    print("⏰ Reminder monitor on")
    while True:
        try:
            agent.scheduler.process_due()
        except Exception as e:
            print(f"⚠️ Reminder tick error: {e}")
        await asyncio.sleep(10)


async def _speak(agent, session, text: str):
    try:
        await session.generate_reply(instructions=f"Reminder: {text}")
    except Exception as e:
        print(f"⚠️ Reminder speak failed: {e}")


async def _morning_brief(agent, session):
    await asyncio.sleep(3)
    brief = await _gather_brief(agent)
    if not brief:
        return
    try:
        await session.generate_reply(
            instructions=f"{brief}\n\nIntroduce this brief naturally and warmly."
        )
    except Exception as e:
        print(f"⚠️ Morning brief failed: {e}")


async def _gather_brief(agent) -> str:
    try:
        if os.getenv("ZENITH_MORNING_BRIEF", "on").lower() not in ("on", "1", "true", "yes"):
            return ""
        
        # Only show morning brief before 12 PM
        from datetime import datetime
        current_hour = datetime.now().hour
        if current_hour >= 12:
            return ""
        
        parts = []
        try:
            from Tools.time_volume_bright import get_time_info, get_weather
            t = await get_time_info()
            parts.append(str(t))
        except Exception:
            pass
        try:
            from Tools.news_provider import get_top_news
            parts.append(str(await get_top_news()))
        except Exception:
            pass
        if agent and agent.scheduler:
            rem = agent.scheduler.list()
            upcoming = [r for r in rem if r["remind_at"] > datetime.now().isoformat()][:3]
            if upcoming:
                parts.append("Today's reminders: " + "; ".join(r["text"] for r in upcoming))
        if agent and agent.memory:
            try:
                stats = agent.memory.stats()
                parts.append(f"You have {stats.get('facts',0)} stored facts and {stats.get('messages',0)} message memories.")
            except Exception:
                pass
        # Dream Mode morning digest — what Zenith learned while user was away
        try:
            from Tools.dream_mode import latest_dream_brief_line
            line = latest_dream_brief_line()
            if line:
                parts.append(line)
        except Exception:
            pass
        # Time capsules that unlocked overnight
        try:
            from Tools.time_capsule import newly_unlocked_brief_line
            line = newly_unlocked_brief_line()
            if line:
                parts.append(line)
        except Exception:
            pass
        return "\n".join(parts)
    except Exception as e:
        print(f"⚠️ Brief gather error: {e}")
        return ""


def _run_light_index(agent):
    """Run lightweight indexing in background - limits files to prevent
    starving the voice agent of responsiveness."""
    try:
        brain = agent.brain
        if not (brain and brain.rag_pipeline):
            print("⚠️ RAG pipeline not available; skipping auto-index")
            return

        from whole_disk_indexer import WholeDiskIndexer

        indexer = WholeDiskIndexer(
            vector_store=brain.rag_pipeline.vector_store,
            embedder=brain.rag_pipeline.embedder,
            content_extractor=brain.rag_pipeline.content_extractor,
            chunker=brain.rag_pipeline.chunker,
        )
        # LIMITED indexing: only 20 files per pass so voice agent stays responsive
        # Indexing resumes automatically across passes/restarts via state file.
        result = indexer.index_content(limit=20)
        print(f"📁 Light index pass complete: {result}")
    except Exception as e:
        print(f"⚠️ Light index worker failed: {e}")


async def _spawn_cloud_client():
    """Launch cloud/laptop_client.py as a child process when configured."""
    url = os.environ.get("ZENITH_CLOUD_URL", "").strip()
    pin = os.environ.get("BRIDGE_PIN", "").strip()
    if not url or not pin:
        logger.warning(
            "Zenith Cloud disabled - set ZENITH_CLOUD_URL and BRIDGE_PIN in .env"
        )
        return
    root = Path(__file__).resolve().parent
    try:
        proc = await asyncio.create_subprocess_exec(
            os.sys.executable, str(root / "cloud" / "laptop_client.py"),
            cwd=str(root),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        logger.info("Zenith Cloud daemon started (pid %s) -> %s", proc.pid, url)
    except Exception as e:
        logger.error("Failed to start Zenith Cloud daemon: %s", e)


async def _auto_index_files(agent):
    await asyncio.sleep(10)
    print("📁 Starting lightweight auto-index (press Ctrl+C to skip)...")
    try:
        await asyncio.to_thread(_run_light_index, agent)
    except Exception as e:
        print(f"⚠️ Auto-index failed: {e}")


def _run_full_index(agent):
    """Run the whole-laptop content scan on a background thread so the
    voice agent stays fully responsive (commands + conversation) while
    training proceeds."""
    try:
        brain = agent.brain
        if not (brain and brain.rag_pipeline):
            print("⚠️ RAG pipeline not available; skipping auto-index")
            return

        from whole_disk_indexer import WholeDiskIndexer

        indexer = WholeDiskIndexer(
            vector_store=brain.rag_pipeline.vector_store,
            embedder=brain.rag_pipeline.embedder,
            content_extractor=brain.rag_pipeline.content_extractor,
            chunker=brain.rag_pipeline.chunker,
        )
        # Passes bounded so we never starve the audio/conversation; index
        # resumes automatically across passes/restarts via state file.
        result = indexer.index_content(limit=0)
        print(f"📁 Auto-index pass complete: {result}")
    except Exception as e:
        print(f"⚠️ Auto-index worker failed: {e}")


def _consolidate_memory(agent):
    """On shutdown, distill the session's conversation into durable facts."""
    try:
        if not (agent and agent.memory):
            return
        llm = None
        try:
            from Tools._llm_client import chat_complete_sync, current_provider

            class ProviderAdapter:
                def generate(self, prompt: str) -> str:
                    reply = chat_complete_sync(prompt, max_tokens=2500)
                    return reply if not reply.startswith("ERROR:") else "[]"

            llm = ProviderAdapter()
        except Exception:
            llm = None
        result = agent.memory.consolidate(llm)
        agent.memory.flush_vectors()
        print(f"🧠 Memory consolidated: {result}")
    except Exception as e:
        print(f"⚠️ Consolidation error: {e}")

# =========================
# RUNNER
# =========================
if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )
