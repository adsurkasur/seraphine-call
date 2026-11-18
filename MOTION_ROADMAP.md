# Proposed coherent upper-body sway

Status: proposal only, not in the renderer or deployed release.

The current source is a whole-PNG swap. Do not silently turn it into a cutout rig. A small isolated mesh-warp prototype could keep feet/lower body fixed, gradually blend displacement above the waist, and move head/upper torso coherently. Apply the same mesh coordinates to every sprite, preserving the mouth/blink selection, baseline and facial proportions. No new artwork or automatic facial generation.

Begin with thinking-only sway, approximately +/-1 degree equivalent, slow eased direction changes, and a strict stop/reset on state changes. Reduced motion uses the existing static avatar. Compare neutral/listening/thinking/blink/talk transitions for face distortion, hair attachment, waist seams and baseline changes. Reject the prototype if it stretches faces or exposes inconsistent geometry. A full joint rig requires separated artwork and hidden coverage; the supplied whole PNGs do not contain that information.
