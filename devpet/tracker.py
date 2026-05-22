"""DevPet tracker — hooks into deterministic-brain tracing to build pet state."""
from __future__ import annotations
import json
import time
import sqlite3
from typing import Dict

from .models import DevPet, ToolBranch, WorkFingerprint, Tier


# Tool → branch mapping
TOOL_BRANCH_MAP = {
    # Version Control
    "git": "version_control", "mercurial": "version_control", "hg": "version_control",
    # CI/CD
    "github_actions": "ci_cd", "jenkins": "ci_cd", "gitlab_ci": "ci_cd",
    "circleci": "ci_cd", "travis": "ci_cd",
    # Testing
    "pytest": "testing", "jest": "testing", "cypress": "testing",
    "unittest": "testing", "mocha": "testing",
    # Containers
    "docker": "containers", "kubernetes": "containers", "k8s": "containers",
    "podman": "containers",
    # Databases
    "postgres": "databases", "mysql": "databases", "mongodb": "databases",
    "redis": "databases", "sqlite": "databases",
    # APIs
    "rest": "apis", "graphql": "apis", "grpc": "apis", "openapi": "apis",
    # Frontend
    "react": "frontend", "vue": "frontend", "angular": "frontend",
    "css": "frontend", "html": "frontend",
    # Low-level
    "rust": "low_level", "c": "low_level", "cpp": "low_level",
    "assembly": "low_level", "llvm": "low_level",
    # AI/ML
    "pytorch": "ai_ml", "tensorflow": "ai_ml", "llm": "ai_ml",
    "openai": "ai_ml", "anthropic": "ai_ml",
    # Security
    "bandit": "security", "owasp": "security", "sonar": "security",
    # Docs
    "markdown": "docs", "sphinx": "docs", "mkdocs": "docs",
    # Debugging
    "gdb": "debugging", "lldb": "debugging", "pdb": "debugging",
    # Performance
    "profiler": "performance", "benchmark": "performance", "criterion": "performance",
}

# Event type → XP mapping
EVENT_XP = {
    "commit": (10, "version_control"),
    "push": (5, "version_control"),
    "pull_request": (15, "version_control"),
    "merge": (20, "version_control"),
    "rebase": (12, "version_control"),
    "ci_pass": (8, "ci_cd"),
    "ci_fail": (2, "ci_cd"),
    "deploy": (25, "ci_cd"),
    "pipeline_config": (30, "ci_cd"),
    "test_pass": (5, "testing"),
    "test_fail": (1, "testing"),
    "test_write": (10, "testing"),
    "coverage_check": (8, "testing"),
    "docker_build": (15, "containers"),
    "docker_run": (5, "containers"),
    "compose_up": (20, "containers"),
    "db_query": (3, "databases"),
    "db_migration": (20, "databases"),
    "api_call": (3, "apis"),
    "api_define": (15, "apis"),
    "frontend_render": (5, "frontend"),
    "css_edit": (3, "frontend"),
    "compile": (5, "low_level"),
    "binary_build": (15, "low_level"),
    "model_train": (25, "ai_ml"),
    "inference": (5, "ai_ml"),
    "security_scan": (15, "security"),
    "vuln_patch": (20, "security"),
    "doc_write": (5, "docs"),
    "debug_session": (10, "debugging"),
    "breakpoint": (3, "debugging"),
    "profile": (10, "performance"),
    "optimize": (15, "performance"),
    "session_start": (2, None),
    "session_end": (5, None),
    "task_complete": (10, None),
    "file_write": (2, None),
    "linter_pass": (3, None),
}


class DevPetTracker:
    """Tracks tool usage from traces and builds DevPet state."""

    def __init__(self, db_path: str = "traces.db", pet_name: str = "DevPet"):
        self.db_path = db_path
        self.pet_name = pet_name
        self.branches: Dict[str, ToolBranch] = {}
        self.events_cache: List[Dict] = []
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=5.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def close(self):
        """Close the SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def load_events(self) -> List[Dict]:
        """Load all events from trace DB."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT ts, event, data FROM events ORDER BY ts"
        )
        events = []
        for row in cursor:
            try:
                data = json.loads(row["data"]) if row["data"] else {}
                events.append({
                    "ts": row["ts"],
                    "event": row["event"],
                    "data": data,
                })
            except (json.JSONDecodeError, TypeError):
                continue
        self.events_cache = events
        return events

    def process_events(self) -> DevPet:
        """Process events and return a DevPet object."""
        if not self.events_cache:
            self.load_events()

        # Initialize branches
        self.branches = {
            name: ToolBranch(name=name, tier=Tier.NOVICE, xp=0)
            for name in set(TOOL_BRANCH_MAP.values())
        }

        total_xp = 0
        event_counts = {}
        languages = {}
        environments = set()
        sessions = 0
        task_completion_times = []
        ci_passes = 0
        ci_total = 0
        last_session_start = None

        for evt in self.events_cache:
            event_type = evt["event"]
            data = evt["data"]
            event_counts[event_type] = int(event_counts.get(event_type, 0)) + 1

            # Add XP based on event
            if event_type in EVENT_XP:
                xp, branch_name = EVENT_XP[event_type]
                if branch_name and branch_name in self.branches:
                    self.branches[branch_name].xp += xp
                    self.branches[branch_name].events[event_type] = \
                        self.branches[branch_name].events.get(event_type, 0) + 1
                total_xp += xp

            # Track languages
            lang = data.get("language") or data.get("lang")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1

            # Track environments
            env = data.get("environment") or data.get("env")
            if env:
                environments.add(env)

            # Session tracking
            if event_type == "session_start":
                sessions += 1
                last_session_start = evt["ts"]
            elif event_type == "session_end" and last_session_start:
                duration = evt["ts"] - last_session_start
                task_completion_times.append(duration)
                last_session_start = None

            # CI tracking
            if event_type in ("ci_pass", "ci_fail"):
                ci_total += 1
                if event_type == "ci_pass":
                    ci_passes += 1

        # Calculate signature moves for each branch
        for name, branch in self.branches.items():
            branch.signature_moves = self._calc_signature_moves(name, branch)

        # Create DevPet
        developer_id = self._calc_developer_id()
        primary_lang = max(languages, key=languages.get) if languages else "unknown"
        ci_pass_rate = ci_passes / ci_total if ci_total > 0 else 0.0
        avg_task = (sum(task_completion_times) / len(task_completion_times)
                    if task_completion_times else 0.0)

        # Pre-compute languages list (avoid syntax error in constructor)
        languages_list = (
            [{"name": k, "percentage": v / sum(languages.values())}
             for k, v in languages.items()] if languages else []
        )

        work_fingerprint = WorkFingerprint(
            session_count=sessions,
            total_coding_minutes=int(sum(task_completion_times) / 60) if task_completion_times else 0,
            avg_task_completion_seconds=avg_task,
            ci_pass_rate=ci_pass_rate,
            tools_used_distinct=len([b for b in self.branches.values() if b.xp > 0]),
            primary_language=primary_lang,
            languages=languages_list,
            environments=list(environments),
            problem_patterns=self._detect_patterns(event_counts),
        )

        pet = DevPet(
            pet_name=self.pet_name,
            species=self._calc_species(),
            archetype=self._calc_archetype(),
            developer_id=developer_id,
            display_name=self._calc_display_name(),
            created_at=self._format_time(self.events_cache[0]["ts"] if self.events_cache else time.time()),
            last_updated=self._format_time(time.time()),
            work_fingerprint=work_fingerprint,
            tool_branches={k: v for k, v in self.branches.items() if v.xp > 0},
        )

        # Calculate stats
        from .stats import calculate_stats, calculate_pet_level
        pet.battle_stats = calculate_stats(pet)
        pet.level, pet.evolution_stage = calculate_pet_level(pet)
        pet.update_visual_traits()

        return pet

    def _calc_signature_moves(self, branch_name: str, branch: ToolBranch) -> List[str]:
        """Generate signature move names based on branch and tier."""
        move_map = {
            "version_control": ["CleanHistory", "BisectBlitz", "RebaseRush", "MergeMaelstrom"],
            "ci_cd": ["PipelineParry", "GreenBuildGuard", "DeployDash", "RollbackRipple"],
            "testing": ["CoverageCloak", "AssertAegis", "MockMirage", "TestTornado"],
            "containers": ["ContainerSwarm", "ImageImpact", "ComposeCrusher", "OrchestrationOrb"],
            "databases": ["QueryQuake", "MigrationMold", "IndexImpale", "TransactionTide"],
            "apis": ["EndpointEagle", "SchemaShield", "PayloadPierce", "RESTStrike"],
            "frontend": ["ReactRampage", "StyleStorm", "DOMDragon", "FlexFlurry"],
            "low_level": ["PointerPummel", "MemoryMaelstrom", "RegisterRush", "BinaryBlitz"],
            "ai_ml": ["TensorTornado", "ModelMeteor", "InferenceImpulse", "NeuralNova"],
            "security": ["VulnVanguard", "PatchPulse", "ScanShield", "FirewallFist"],
            "docs": ["DocDazzler", "ReadmeRush", "MarkdownMist", "GuideGale"],
            "debugging": ["BreakpointBash", "StackStrike", "TraceThunder", "GdbGale"],
            "performance": ["ProfilePulse", "OptimizeOrb", "BenchmarkBlitz", "CacheCrush"],
        }
        moves = move_map.get(branch_name, ["GenericGrowl"])
        # Number of moves based on tier
        count = min(branch.tier.value, len(moves))
        return moves[:count]

    def _calc_developer_id(self) -> str:
        import hashlib
        return hashlib.sha256(f"devpet_{self.pet_name}".encode()).hexdigest()[:16]

    def _calc_display_name(self) -> str:
        return f"Dev_{self.pet_name}"

    def _calc_species(self) -> str:
        if not self.branches:
            return "BasicBlob"
        primary = max((b for b in self.branches.values() if b.xp > 0),
                       key=lambda b: b.xp, default=None)
        if not primary:
            return "BasicBlob"
        type_map = {
            "version_control": "VoltSprite",
            "ci_cd": "SteelGolem",
            "testing": "FairyMoth",
            "containers": "WaveWraith",
            "databases": "VineViper",
            "apis": "MindMantis",
            "frontend": "FlameFox",
            "low_level": "ShadowWolf",
            "ai_ml": "DragonWyrmling",
            "security": "PhantomBat",
            "docs": "QuillQuokka",
            "debugging": "FistFalcon",
            "performance": "StoneSloth",
        }
        return type_map.get(primary.name, "BasicBlob")

    def _calc_archetype(self) -> str:
        if not self.branches:
            return "Novice"
        from .stats import calculate_stats
        # Create temp pet to get stats
        temp_stats = calculate_stats(DevPet(
            pet_name="temp", species="", archetype="",
            developer_id="", display_name="",
            created_at="", last_updated="",
            tool_branches={k: v for k, v in self.branches.items() if v.xp > 0}
        ))
        stat_map = temp_stats.to_dict()
        dominant = max(stat_map, key=stat_map.get)
        archetype_map = {
            "velocity": "SpeedDemon",
            "precision": "CodeSniper",
            "breadth": "Polyglot",
            "depth": "Specialist",
            "resilience": "Trouper",
            "ingenuity": "Innovator",
        }
        return archetype_map.get(dominant, "Novice")

    def _detect_patterns(self, event_counts: Dict) -> List[str]:
        patterns = []
        if event_counts.get("test_write", 0) > event_counts.get("task_complete", 1) * 0.5:
            patterns.append("test-driven")
        if event_counts.get("linter_pass", 0) > 10:
            patterns.append("clean-code")
        if event_counts.get("rebase", 0) > 5:
            patterns.append("refactor-first")
        if event_counts.get("doc_write", 0) > 5:
            patterns.append("docs-first")
        if event_counts.get("debug_session", 0) > event_counts.get("task_complete", 1) * 0.3:
            patterns.append("debug-heavy")
        return patterns

    @staticmethod
    def _format_time(timestamp: float) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(timestamp).isoformat()
