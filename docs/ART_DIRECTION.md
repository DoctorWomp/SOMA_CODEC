# Art Direction & Rendering Budget

**Status:** APPROVED (owner, 2026-11-13)
**Related:** [RANGE_V0_SCOPE.md](RANGE_V0_SCOPE.md) · [INFERENCE_STRATEGY.md](INFERENCE_STRATEGY.md) (VRAM budget) · [DECISIONS.md](DECISIONS.md) D-14 (palettes, light safety), D-26 · Avatar Foundry v0.1 §3, §5 · Blueprint §5.2, §14

How RANGE should look, how much GPU it may spend on looks, and how lighting and atmosphere become part of what avatars perceive rather than decoration.

**Principle:** *spend compute on the minds, not the pixels*. The GPU is shared with the models: every frame rendered competes with token generation for both VRAM **and** GPU time. Visual fidelity is added only when it passes a measured "render tax" budget (§7).

---

## 1. Visual target

**Low-poly 3D diorama**: faceted geometry, flat or near-flat shading, a small strong palette, clear silhouettes, crisp contrast. Style 5 in the [visual styles reference](concept-art/reference_visual_styles_atlas.webp), with the expo layout and mood of [Expo Hall v0.1](concept-art/range_expo_hall_v0.1_top_down.webp) and the [Robot R concept](concept-art/range_expo_robot_r_concept.webp).

Why it fits:
- **Readability over detail.** Posture, head direction, gestures and grouping, the cues HORIZON is about, read best with clean silhouettes.
- **Cheap.** Low triangle counts and one shared palette texture leave most of the GPU for inference.
- **Honest.** Stylized visuals don't pretend to be camera-realistic sensing (D-16).

## 2. Robot avatars

Baseline: the [low-poly humanoid concept](concept-art/robot_avatar_lowpoly_concept.jpg). It is plausible next to real humanoid robots, readable at a distance, and cheap.

| Feature | Use in RANGE |
|---|---|
| **Black visor** | The **Beacon face display**: ASCII face glyphs (`^_^`, `U_U`, `~_~`, D-14) rendered on the visor as an emissive texture |
| **Ear pods / neck band** | **Beacon light**: the six-state public palette as an emissive strip, always paired with words (D-14) |
| **Head direction** | The strongest social signal: where the robot is attending. Driven by Focus (L4) through look-at, so attention is visible |
| **Articulated limbs** | Gestures: nod, wave, point, open-palm "one moment", lean in, step back, yield |
| **Colored variants** | Identity at a glance in multi-robot sandbox scenes (§2.1) |

### 2.1 Identity colors vs Beacon colors

The concept's variant colors (orange, red, blue, green, purple) overlap with the **Beacon palette**, where red means "stop/boundary" and orange means "caution" (D-14). A red-bodied robot could be misread as signaling "stop".

Rules:
- **Body color = identity, matte and constant.** It appears only on fixed trim panels (shoulders, forearms, chest band).
- **Beacon state = emissive light, changes over time, always with words.** It appears only on the visor and light strip.
- Identity is never color-only: each robot also has a **number badge** and a distinct trim *pattern*, for colorblind readability.
- **Controlled trials:** robots under A/B comparison look identical; any color is counterbalanced across arms (Avatar Foundry §1).

### 2.2 Human avatars

Same faceted style and shared skeleton. Variety comes from palette, proportions and accessories (badge, backpack, jacket, cup). Mobility-aid variants are included (Foundry §3). **Appearance never encodes worth, trustworthiness or hidden intent** (Foundry §3, D-13): the skeptic and the "villain-coded" look are explicitly avoided.

## 3. Rendering approach (Godot)

| Area | v0 approach | Why |
|---|---|---|
| Renderer | Forward+ (desktop) | Supports everything we may need later (fog, glow) on the RTX 4070 Ti Super |
| Materials | **One shared palette texture**: every model's faces are UV-mapped onto a small color grid. One material for most of the world | Very few draw calls; recoloring the whole venue is one image edit |
| Shading | Flat normals, standard material, matte roughness; emissive only for screens and Beacon | Faceted look; emissive becomes meaningful (screens, signs, robot faces) |
| Static lighting | **Baked lightmaps** (`LightmapGI`) for the hall | Soft, good-looking light at almost zero runtime cost |
| Dynamic light | One directional light with limited-distance shadows; a few unshadowed point lights for practicals | Shadows where they matter (avatars near the camera) |
| Ambient occlusion | Off at V0; light SSAO at V1 | Grounds objects cheaply |
| Glow | On at V1, subtle | Makes visors, screens and signs pop |
| Fog / atmosphere | Off at V0; local volumes at V2 (§5) | Expensive; only where it means something |
| Crowds and props | `MultiMesh` instancing; LODs (Blueprint §5.2) | Hundreds of objects for little cost |
| Frame rate | **Capped** (60 FPS default, 30 in research mode); headless mode for sweeps | Uncapped rendering steals GPU time from the models |

### 3.1 Budgets (starting targets, to measure)

| Item | Target |
|---|---|
| Rendering VRAM | ≤ ~1.5 GB (fits the [inference VRAM budget](INFERENCE_STRATEGY.md) §5) |
| Focal avatars | ~1–4K triangles each |
| Crowd avatars | ~0.2–1K triangles each, LOD beyond ~15 m |
| Textures | One palette atlas + a few small (≤512 px) screen and sign textures |
| Shadowed lights | 1 directional |
| Unshadowed dynamic lights | ≤ ~8 visible |
| Frame time | 60 FPS at 1080p/1440p with models idle; record FPS while models run |

## 4. Physics

| Need | Approach |
|---|---|
| Avatars | Kinematic character bodies (`CharacterBody3D`) with navigation and avoidance. No ragdolls (fidelity P0/P1, Foundry §5) |
| Static world | Primitive colliders (boxes, capsules), separate from the visible mesh |
| Dynamic props | A few rigid bodies: carts, crates, dropped brochures, a knocked-over cone |
| Zones and senses | `Area3D` volumes for zones, earshot and lighting/fog regions; raycasts for line of sight |
| Tick | Fixed 60 Hz physics, independent of rendering and models |
| Engine | Godot's built-in physics; evaluate the Jolt option at G1 if stacking or carts misbehave |

Replays use recorded events, not physics re-simulation, so physics determinism across machines isn't required (Blueprint §13.3).

## 5. Environment that matters to behavior

Lighting, atmosphere and sound are **scenario variables that affect simulated perception**, not just mood. The key rule: **one source of truth.** Each zone or volume in the map file declares a few environment values. The renderer uses them to *look* right, and the sensor model uses them to compute what avatars *perceive*. Sensors never read rendered pixels; we run no vision models (D-16). So what the spectator sees and what the agent perceives always agree.

```yaml
# configs/maps/expo_hall_a.yaml (illustrative)
zones:
  demo_stage:
    light_level: 0.35          # dim house lights during shows
    visual_range_factor: 0.6   # haze machine
    noise_floor_db: 72         # speakers
    light_preset: neon_two_tone
  main_entrance:
    light_level: 0.9
    backlit: true              # glass doors: silhouettes, faces hard to read
  lounge:
    light_level: 0.5
    noise_floor_db: 55
    light_preset: warm_practical
```

| Environment variable | Looks like | Perception effect | What it tests |
|---|---|---|---|
| **Low light** | Low-key stage, dim lounge | Shorter gesture-detection range; more `DEGRADED` observations | Does Haze rise instead of R guessing? |
| **Backlight** | Silhouettes at the glass entrance | Head direction and small gestures unreliable | Source and bid uncertainty |
| **Haze / fog volume** | Stage haze machine | Reduced visual range inside the volume | Treating unseen as `UNKNOWN`, not empty |
| **Noise floor** | Speakers, café chatter | Lower speech-detection confidence, more misheard words | Confirming more often; switching to gestures |
| **Crowd density** | Packed aisles | More occlusion | Peripheral bids, attention |
| **Glare / bright screens** | Display walls | Local visual degradation | Robustness |

**Communication adapts to the environment too.** R's own Beacon is perceived by others under the same rules: a face glyph is legible only within some distance and light level, and a light strip carries further in the dark. In a noisy zone, gestures beat speech. This gives a measurable research question: **does R choose the right channel for the conditions** (speak, gesture, light, move closer)?

**Lighting presets** (from the [lighting reference](concept-art/reference_lighting_language_atlas.webp)) become scenario settings: *day expo* (high-key), *stage show* (low-key + neon two-tone), *after hours* (cool moonlight + warm practicals). Atmosphere presets (from the [atmosphere reference](concept-art/reference_atmosphere_environment_atlas.webp)): *clear air*, *thin haze*, *stage haze*, *dust motes in light beams*. Each preset has a cost measured under §7.

These effects are simple proxies, labeled synthetic, not models of real optics or acoustics.

## 6. Body language and animation

| Item | Approach |
|---|---|
| Skeleton | One shared humanoid skeleton for robots and humans, so animations retarget across bodies |
| Core set | Idle, walk, turn, stop, sit, nod, shake, wave, point, beckon, open-palm "one moment", lean in, step back, shrug, listening posture, waiting posture |
| Procedural layers | Head/gaze look-at (attention), gesture amplitude and tempo from Foundry sliders, breathing idle for humans |
| Robot extras | Visor glyph keyframes and light patterns (reaction lanes → keyframes, Chatbot spec A2.9); ≤ 3 Hz flashing (D-14) |
| Asset sources | Free low-poly packs with permissive (CC0) licenses for props, characters and animations, e.g. Kenney and Quaternius. **Verify each pack's license before use**; record it in `THIRD_PARTY_LICENSES` |
| Robot mesh | v0: assembled from primitives in Godot to match the concept's proportions and joints. Later: a proper mesh modeled from the concept (Blender) on the **same skeleton and joint names**, so nothing else changes |

Gestures are actions in the bounded vocabulary (`GESTURE`, `LOOK_AT`, `TURN_TO`). The model picks *which* gesture; animation plays it. The model never animates joints directly.

## 7. Fidelity ladder

Each level is reached only after the one below works and passes the **render tax** test: the same scenario run with rendering off and at the new level, comparing focal model tokens/s, decision latency p50/p95, NPC throughput and FPS. Proposed limit: rendering may cost **≤ 10%** of focal-model throughput.

| Level | Gate | Looks | Contents |
|---|---|---|---|
| **V0 Greybox** | G1–G5 (Sandbox Flats) | Flat colors, capsules and boxes, primitive robot, one light, no shadows | Proves interaction, perception, HORIZON |
| **V1 Low-poly diorama** | G6 (Expo Hall A) | Modular booths and props from the palette atlas, faceted robot and humans, baked lighting, one shadowed light, subtle glow and SSAO | Looks like the concept art at modest cost |
| **V2 Atmosphere** | After v0 | Lighting and atmosphere presets, local haze volumes, emissive screens, dust motes, ambient life | Environment-as-variable experiments (§5) |
| **V3 Polish** | Later | Post-processing, cinematic cameras, nicer UI transitions | Presentation and demos |

Headless mode (no rendering) is always available for ablation sweeps.

## 8. HUD vs world

The operator HUD and layer viewer use their own diagnostic look (dark panels, cyan accents, like the concept atlases) so they are never confused with in-world objects or Beacon signals. HUD meaning is never color-only; patterns and labels back it up (Atlas §9, D-14).
