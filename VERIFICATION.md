# Current release: procedural sway integration

Current frontend includes the approved state-specific waist/neck mesh, with pinned lower body, actual-audio mouth/blink and PNG fallback. The production directory has no prototype HTML or debug controls. Main source release follows production call-v8-20261119-03; backend structured-response leak fix is unchanged.

New checks: actual opposite-pose screenshots differ above the waist but match below source y340; reduced-motion all-zero pose; visible fallback after simulated WebGL context loss and WebGL unavailability. Existing controls, Kokoro playback, voice-interrupt and farewell tests also passed locally. Public deployed browser validation passed: release03 mesh loaded, prototype URL404, simulated mic interrupt stopped genuine Kokoro playback, real server STT transcribed audio, a real chat/Kokoro farewell showed both mouth states and moving mesh, then ended in sleep without page errors. The microphone signal in interrupt validation is synthetic; physical microphone/room acoustics are not established. Native Telegram/physical mobile performance is not claimed.

## Earlier release context (historical)

The originating release was deployed with frontend/backend backups and rollback checks. Public browser verification passed: seven sprites loaded, genuine server STT transcribed a WAV, a real model reply produced Kokoro audio, both mouth states appeared, output drove button feedback, and a goodbye ended in sleep state after playback. The exact reported malformed JSON shape was added to regression tests and is rejected before TTS.

The public snapshot parameterizes paths/endpoints and user identity, replaces a private STT power-management client with a portable HTTP adapter, and disables Agent mode by default. Unit tests and static-page smoke checks cover these export changes. External services are prerequisites and are not launched by tests.

Not established: physical microphone reliability on every device, acoustic echo cancellation in every room, Android/Telegram native frame pacing, semantic correctness of every goodbye, Agent tool execution, or upper-body mesh animation. No claim of pixel-perfect independently generated artwork.
