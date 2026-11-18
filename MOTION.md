# Production PNG sway

Whole-PNG swapping with a small native WebGL mesh, not Live2D or cutout skeletal artwork. One clock and mesh map every frame; texture changes crossfade45ms without resetting joint pose. The 369-vertex/640-triangle mesh has waist(157,270) and neck(157,190) control pivots on a320x480 source canvas. Source y>=310 is fixed. Head/face above the neck falloff move rigidly; waist/neck transitions use smooth weights.

## Profiles

| State | Body amplitude | Neck amplitude | Main period |
|---|---:|---:|---:|
| Idle |2.5deg|1deg|5.2s|
| Listening |3.3deg|1.5deg|5.8s|
| Thinking |6.1deg|2.25deg|4.2s|
| Speaking |4.5deg|1.7deg|3.8s|
| Sleep/ended |1.35deg|1.4deg|7.6s|

These are tuning amplitudes before layered oscillation and smooth settling, not claims of perspective rotation. Listening includes a small attention lean; thinking has asymmetric drift; speaking adds restrained head emphasis from actual playback energy. Sleep adds up to3 source pixels of head dip. Mouth/blink use the existing actual-audio selection logic and supplied whole PNGs.

`prefers-reduced-motion` makes all joint displacement exactly zero. Missing WebGL/shader support or runtime context loss leaves a visible PNG avatar with the same mouth/blink state. GPU resources are released at teardown. Rendering skips hidden documents. No runtime engine/dependency was added.

No skeleton UI, strength slider, pose inspector or prototype route is included in the production directory. Development exploration remains outside the shipped main tree.

## Verified scope and limitations

Browser-rendered opposite thinking poses visibly differ; screenshot comparison found24,055 changed pixels overall and zero changed pixels below source y340. Reduced-motion, context-loss fallback and unavailable-WebGL fallback were exercised. Local control, actual cached Kokoro playback, mouth/blink, interruption, and farewell regression paths were exercised. Source-frame differences are not fixed by the rig; there is no hidden anatomical coverage or full joint articulation. Physical Android/Telegram GPU behavior and every room's acoustic interruption behavior still need device testing.
