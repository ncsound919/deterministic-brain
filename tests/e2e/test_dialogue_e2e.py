"""E2E Tests for Dialogue/Voice Pipeline."""
from __future__ import annotations


class TestInputNormalization:
    """Test input normalization layer."""

    def test_normalizer_initialization(self):
        """InputNormalizer should initialize."""
        from dialogue.input_normalizer import InputNormalizer
        
        normalizer = InputNormalizer()
        
        assert normalizer is not None

    def test_unicode_normalization(self):
        """Should normalize unicode characters."""
        from dialogue.input_normalizer import InputNormalizer
        
        normalizer = InputNormalizer()
        
        result = normalizer.normalize("café")
        
        assert result.text == "café"

    def test_abbreviation_expansion(self):
        """Should expand common abbreviations."""
        from dialogue.input_normalizer import InputNormalizer
        
        normalizer = InputNormalizer()
        
        result = normalizer.normalize("plz help me")
        
        assert "please" in result.text.lower()

    def test_whitespace_normalization(self):
        """Should normalize whitespace."""
        from dialogue.input_normalizer import InputNormalizer
        
        normalizer = InputNormalizer()
        
        result = normalizer.normalize("hello    world")
        
        assert "  " not in result.text


class TestNLULayer:
    """Test NLU layer."""

    def test_nlu_pipeline_initialization(self):
        """NLU pipeline should initialize."""
        from dialogue.nlu_layer import NLUPipeline
        
        pipeline = NLUPipeline()
        
        assert pipeline is not None

    def test_intent_classification_greeting(self):
        """Should classify greeting intent."""
        from dialogue.nlu_layer import SnipsStyleIntentClassifier
        
        classifier = SnipsStyleIntentClassifier()
        
        intent, confidence = classifier.classify("hello there")
        
        assert intent.value == "greeting"
        assert confidence >= 0.5

    def test_intent_classification_farewell(self):
        """Should classify farewell intent."""
        from dialogue.nlu_layer import SnipsStyleIntentClassifier
        
        classifier = SnipsStyleIntentClassifier()
        
        intent, confidence = classifier.classify("goodbye")
        
        assert intent.value == "farewell"

    def test_intent_classification_command(self):
        """Should classify command intent."""
        from dialogue.nlu_layer import SnipsStyleIntentClassifier
        
        classifier = SnipsStyleIntentClassifier()
        
        intent, confidence = classifier.classify("create a component")
        
        assert intent.value == "command"

    def test_intent_classification_question(self):
        """Should classify question intent."""
        from dialogue.nlu_layer import SnipsStyleIntentClassifier
        
        classifier = SnipsStyleIntentClassifier()
        
        intent, confidence = classifier.classify("what is this?")
        
        assert intent.value == "question"

    def test_slot_extraction_command(self):
        """Should extract slots from commands."""
        from dialogue.nlu_layer import SnipsStyleIntentClassifier, Intent
        
        classifier = SnipsStyleIntentClassifier()
        
        slots = classifier.extract_slots("create a component named Button", Intent.COMMAND)
        
        assert isinstance(slots, dict)

    def test_full_nlu_pipeline(self):
        """Full NLU pipeline should process input."""
        from dialogue.nlu_layer import NLUPipeline
        
        pipeline = NLUPipeline()
        
        result = pipeline.process("hello world")
        
        assert result is not None
        assert hasattr(result, "intent")
        assert hasattr(result, "slots")


class TestDialoguePolicy:
    """Test dialogue policy."""

    def test_state_machine_initialization(self):
        """DialogueStateMachine should initialize."""
        from dialogue.dialogue_policy import DialogueStateMachine
        
        sm = DialogueStateMachine()
        
        assert sm is not None
        assert sm.current_state is not None

    def test_state_transition_greeting(self):
        """Should transition on greeting."""
        from dialogue.dialogue_policy import DialogueStateMachine
        
        sm = DialogueStateMachine()
        
        new_state = sm.transition("greeting")
        
        assert new_state is not None

    def test_get_next_action_greeting(self):
        """Should return appropriate action for greeting state."""
        from dialogue.dialogue_policy import DialogueStateMachine
        
        sm = DialogueStateMachine()
        
        class MockNLU:
            intent = type('obj', (object,), {'value': 'greeting'})()
            slots = {}
            entities = []
        
        action = sm.get_next_action(MockNLU())
        
        assert action is not None
        assert action.action_type is not None

    def test_context_update(self):
        """Should update context."""
        from dialogue.dialogue_policy import DialogueStateMachine
        
        sm = DialogueStateMachine()
        
        sm.update_context("user_name", "John")
        
        assert sm.get_context("user_name") == "John"

    def test_state_reset(self):
        """Should reset state."""
        from dialogue.dialogue_policy import DialogueStateMachine
        
        sm = DialogueStateMachine()
        sm.transition("greeting")
        
        sm.reset()
        
        from dialogue.dialogue_policy import DialogueState as DS
        assert sm.current_state == DS.IDLE


class TestResponseRealizer:
    """Test response realization."""

    def test_realizer_initialization(self):
        """TemplateRealizer should initialize."""
        from dialogue.response_realizer import TemplateRealizer
        
        realizer = TemplateRealizer(seed=42)
        
        assert realizer is not None

    def test_realize_greeting(self):
        """Should realize greeting response."""
        from dialogue.response_realizer import create_default_realizer
        
        realizer = create_default_realizer(seed=42)
        
        response = realizer.realize("greeting", {})
        
        assert response is not None
        assert response.text is not None
        assert len(response.text) > 0

    def test_realize_farewell(self):
        """Should realize farewell response."""
        from dialogue.response_realizer import create_default_realizer
        
        realizer = create_default_realizer(seed=42)
        
        response = realizer.realize("farewell", {})
        
        assert response is not None

    def test_slot_filling(self):
        """Should fill slots in templates."""
        from dialogue.response_realizer import create_default_realizer
        
        realizer = create_default_realizer(seed=42)
        
        response = realizer.realize("command", {"action": "create", "object": "button"})
        
        assert "create" in response.text.lower() or "button" in response.text.lower()

    def test_deterministic_realization(self):
        """Realization should be deterministic with seed."""
        from dialogue.response_realizer import create_default_realizer
        
        realizer1 = create_default_realizer(seed=42)
        r1 = realizer1.realize("greeting", {})
        
        realizer2 = create_default_realizer(seed=42)
        r2 = realizer2.realize("greeting", {})
        
        assert r1.text == r2.text


class TestDialoguePipeline:
    """Test complete dialogue pipeline."""

    def test_pipeline_initialization(self):
        """DialoguePipeline should initialize."""
        from dialogue.pipeline import DialoguePipeline
        
        pipeline = DialoguePipeline(seed=42)
        
        assert pipeline is not None

    def test_process_single_turn(self):
        """Should process single dialogue turn."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        pipeline = create_dialogue_pipeline(seed=42)
        
        result = pipeline.process("hello")
        
        assert result is not None
        assert result.input_text == "hello"
        assert result.response is not None
        
        pipeline.close()

    def test_process_multiple_turns(self):
        """Should process multiple turns."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        pipeline = create_dialogue_pipeline(seed=42)
        
        r1 = pipeline.process("hello")
        r2 = pipeline.process("help me")
        r3 = pipeline.process("bye")
        
        assert r1.response is not None
        assert r2.response is not None
        assert r3.response is not None
        
        pipeline.close()

    def test_pipeline_determinism(self):
        """Pipeline should be deterministic."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        outputs = []
        
        for _ in range(2):
            pipeline = create_dialogue_pipeline(seed=42)
            result = pipeline.process("hello")
            outputs.append(result.response)
            pipeline.close()
        
        assert outputs[0] == outputs[1]


class TestDialogueReproducibility:
    """Test dialogue reproducibility."""

    def test_session_logging(self):
        """Should log dialogue sessions."""
        from dialogue.reproducibility import start_dialogue_session, log_dialogue_event, end_dialogue_session
        
        session_id = start_dialogue_session(seed=42)
        
        log_dialogue_event("input", "test", {"test": "data"}, {"result": "ok"})
        
        end_session = end_dialogue_session()
        
        assert end_session is not None

    def test_session_replay(self):
        """Should replay session events."""
        from dialogue.reproducibility import start_dialogue_session, log_dialogue_event, end_dialogue_session, replay_session
        
        session_id = start_dialogue_session(seed=42)
        
        log_dialogue_event("test", "event", {"in": "data"}, {"out": "result"})
        
        end_dialogue_session()
        
        events = replay_session(session_id)
        
        assert isinstance(events, list)


class TestVoiceMode:
    """Test voice mode integration."""

    def test_voice_mode_import(self):
        """Should import voice mode."""
        from features import voice_mode
        
        assert voice_mode is not None

    def test_offline_tts_available(self):
        """Should check offline TTS availability."""
        from features.voice_mode import OfflineTTS
        
        tts = OfflineTTS()
        
        assert tts is not None