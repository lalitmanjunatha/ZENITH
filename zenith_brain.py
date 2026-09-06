import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ZenithBrain:
    def __init__(self):
        self.memory = None
        self.file_indexer = None
        self._initialized = False
        self._init_status = {}

    def initialize(self) -> Dict[str, Any]:
        self._init_status = {}

        try:
            from content_extractor import ContentExtractor
            self.content_extractor = ContentExtractor()
            self._init_status["content_extractor"] = "ready"
        except Exception as e:
            self._init_status["content_extractor"] = f"failed: {e}"

        try:
            from file_indexer import FileIndexer
            self.file_indexer = FileIndexer()
            self._init_status["file_indexer"] = "ready"
        except Exception as e:
            self._init_status["file_indexer"] = f"failed: {e}"

        try:
            from memory_manager import MemoryManager
            self.memory = MemoryManager()
            self._init_status["memory"] = "ready"
        except Exception as e:
            self.memory = None
            self._init_status["memory"] = f"failed: {e}"

        self._initialized = True

        ready_count = sum(1 for v in self._init_status.values() if v == "ready")
        total_count = len(self._init_status)

        return {
            "initialized": True,
            "components_ready": ready_count,
            "total_components": total_count,
            "status": self._init_status,
        }

    def classify_query(self, query: str) -> str:
        query_lower = query.lower()

        rag_keywords = [
            "search my files", "find in my documents", "look up",
            "what did i save", "remember", "retrieve", "from my files",
            "in my notes", "from my data", "my documents",
            "aadhaar", "aadhar", "pan card", "passport", "id number",
            "show me where", "open my", "find my file",
            "tell me my", "what is my", "where is my",
        ]

        file_keywords = [
            "show me", "open", "where is", "locate", "find file",
            "open file", "show folder", "open folder",
        ]

        for kw in rag_keywords:
            if kw in query_lower:
                return "rag"

        for kw in file_keywords:
            if kw in query_lower:
                return "file_open"

        return "llm"

    def match_command(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()

        tool_patterns = {
            "search_web": {
                "keywords": ["search", "google", "look up", "find online", "web search", "google it", "search the web", "search internet", "look up online"],
                "extract_param": lambda q: q,
            },
            "get_weather": {
                "keywords": ["weather", "forecast", "temperature", "how is the weather", "will it rain", "is it hot", "is it cold"],
                "extract_param": lambda q: "current",
            },
            "get_time_info": {
                "keywords": ["time", "what time is it", "current time", "tell me the time", "what's the time", "clock"],
                "extract_param": lambda q: "current",
            },
            "get_system_info_deep": {
                "keywords": ["system info", "computer specs", "what is my system", "system details", "hardware info", "cpu", "ram", "memory info"],
                "extract_param": lambda q: "full",
            },
            "open_app": {
                "keywords": ["open", "launch", "start", "run", "open app", "launch app", "start app", "open application"],
                "extract_param": lambda q: query,
            },
            "manage_window": {
                "keywords": ["manage window", "resize window", "move window", "close window", "minimize", "maximize", "organize windows"],
                "extract_param": lambda q: query,
            },
            "list_windows": {
                "keywords": ["list windows", "open windows", "what windows are open", "show windows", "active windows"],
                "extract_param": lambda q: "list",
            },
            "desktop_control": {
                "keywords": ["desktop", "show desktop", "show my desktop", "minimize all", "show all windows"],
                "extract_param": lambda q: "show",
            },
            "scroll_content": {
                "keywords": ["scroll", "scroll up", "scroll down", "scroll left", "scroll right"],
                "extract_param": lambda q: query,
            },
            "send_whatsapp_message": {
                "keywords": ["whatsapp", "send message", "text someone", "send a text", "whatsapp message"],
                "extract_param": lambda q: query,
            },
            "send_media_to_whatsapp": {
                "keywords": ["send image whatsapp", "send photo whatsapp", "send media whatsapp", "share on whatsapp"],
                "extract_param": lambda q: query,
            },
            "use_smart_clipboard": {
                "keywords": ["clipboard", "copy", "paste", "cut", "clipboard manager"],
                "extract_param": lambda q: query,
            },
            "system_power_action": {
                "keywords": ["shutdown", "restart", "lock", "log off", "sleep", "hibernate", "power off", "turn off", "reboot"],
                "extract_param": lambda q: query,
            },
            "press_key": {
                "keywords": ["press key", "keyboard", "type", "hotkey", "shortcut", "key combo"],
                "extract_param": lambda q: query,
            },
            "control_system_volume": {
                "keywords": ["volume", "mute", "unmute", "volume up", "volume down", "set volume", "loud", "quiet", "sound"],
                "extract_param": lambda q: query,
            },
            "control_screen_brightness": {
                "keywords": ["brightness", "screen brightness", "dim", "bright", "display brightness", "adjust brightness"],
                "extract_param": lambda q: query,
            },
            "screen_short": {
                "keywords": ["screenshot", "screen shot", "capture screen", "take screenshot", "screen capture", "screen grab"],
                "extract_param": lambda q: "full",
            },
            "read_screen_text": {
                "keywords": ["read screen", "what is on screen", "screen text", "ocr", "read what's on screen"],
                "extract_param": lambda q: "current",
            },
            "analyze_screen": {
                "keywords": ["analyze screen", "describe screen", "what do i see", "screen analysis"],
                "extract_param": lambda q: "current",
            },
            "analyze_local_image": {
                "keywords": ["analyze image", "describe image", "what is in this image", "image analysis", "read image"],
                "extract_param": lambda q: query,
            },
            "camera_analysis": {
                "keywords": ["camera", "webcam", "what does camera see", "camera analysis", "capture"],
                "extract_param": lambda q: "capture",
            },
            "open_spotify": {
                "keywords": ["spotify", "play music", "open spotify", "spotify play", "play song", "play playlist"],
                "extract_param": lambda q: query,
            },
            "spotify_play_song": {
                "keywords": ["play song", "play track", "play this song", "play this track"],
                "extract_param": lambda q: query,
            },
            "spotify_pause": {
                "keywords": ["pause", "pause music", "pause spotify", "stop music", "stop spotify"],
                "extract_param": lambda q: "pause",
            },
            "spotify_next": {
                "keywords": ["next", "next song", "next track", "skip", "skip song"],
                "extract_param": lambda q: "next",
            },
            "spotify_previous": {
                "keywords": ["previous", "previous song", "previous track", "back", "back song"],
                "extract_param": lambda q: "previous",
            },
            "spotify_play_liked": {
                "keywords": ["liked songs", "favorites", "liked", "play liked", "play favorites"],
                "extract_param": lambda q: "liked",
            },
            "content_search": {
                "keywords": ["content search", "search by content", "find in content", "search inside files", "search within documents", "search text in files"],
                "extract_param": lambda q: query,
            },
            "open_file_by_content": {
                "keywords": ["open by content", "open file by content", "find and open", "open the file where", "open the document about", "open the file about"],
                "extract_param": lambda q: query,
            },
            "show_folder_contents": {
                "keywords": ["show folder", "list folder", "folder contents", "what is in this folder", "show me the folder", "list contents"],
                "extract_param": lambda q: query,
            },
            "search_by_filename": {
                "keywords": ["search by filename", "find by name", "search file name", "find file by name", "search for file named"],
                "extract_param": lambda q: query,
            },
        }

        matched_tool = None
        best_score = 0
        best_param = None

        for tool_name, pattern in tool_patterns.items():
            for keyword in pattern["keywords"]:
                if keyword in query_lower:
                    score = len(keyword)
                    if score > best_score:
                        best_score = score
                        matched_tool = tool_name
                        best_param = pattern["extract_param"](query)

        if matched_tool:
            return {
                "matched": True,
                "tool_name": matched_tool,
                "param": best_param,
                "confidence": min(best_score / 10.0, 1.0),
            }

        return {
            "matched": False,
            "tool_name": None,
            "param": None,
            "confidence": 0.0,
        }

    def process_query(self, query: str) -> Dict[str, Any]:
        query_type = self.classify_query(query)

        result = {
            "query": query,
            "type": query_type,
            "timestamp": str(__import__("datetime").datetime.now()),
        }

        if query_type == "rag":
            result.update(self._handle_rag(query))
        elif query_type == "file_open":
            result.update(self._handle_file_open(query))
        else:
            result.update(self._handle_llm(query))

        return result

    def _handle_rag(self, query: str) -> Dict[str, Any]:
        return {"message": "RAG search is no longer available (ML components removed).", "query_type": "rag"}

    def _handle_llm(self, query: str) -> Dict[str, Any]:
        return {
            "message": "Query classified as general LLM question.",
            "query_type": "llm",
        }

    def _handle_file_open(self, query: str) -> Dict[str, Any]:
        return {"message": "File search is no longer available (ML components removed).", "query_type": "file_open"}

    def recall_memory(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        if not self.memory:
            return {"error": "Memory manager not initialized"}
        return self.memory.recall(query, top_k=top_k)

    def get_memory_stats(self) -> Dict[str, Any]:
        if not self.memory:
            return {"error": "Memory manager not initialized"}
        return self.memory.stats()

    def get_status(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "components": self._init_status,
        }
