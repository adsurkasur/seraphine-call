# Verification scope

The originating release was deployed with frontend/backend backups and rollback checks. Public browser verification passed: seven sprites loaded, genuine server STT transcribed a WAV, a real model reply produced Kokoro audio, both mouth states appeared, output drove button feedback, and a goodbye ended in sleep state after playback. The exact reported malformed JSON shape was added to regression tests and is rejected before TTS.

The public snapshot parameterizes paths/endpoints and user identity, replaces a private STT power-management client with a portable HTTP adapter, and disables Agent mode by default. Unit tests and static-page smoke checks cover these export changes. External services are prerequisites and are not launched by tests.

Not established: physical microphone reliability on every device, acoustic echo cancellation in every room, Android/Telegram native frame pacing, semantic correctness of every goodbye, Agent tool execution, or upper-body mesh animation. No claim of pixel-perfect independently generated artwork.
