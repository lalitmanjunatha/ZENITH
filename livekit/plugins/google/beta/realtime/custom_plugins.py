# custom_plugins.py
class EffectPlugin:
    _effect_callback = None
    
    @classmethod
    def register_effect_callback(cls, callback):
        cls._effect_callback = callback
        
    @classmethod
    def trigger_effect(cls):
        if cls._effect_callback:
            cls._effect_callback()