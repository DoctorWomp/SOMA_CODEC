# Spatial Self-Model — Research Seeds
**Filed:** 2026-07-06 | **Role:** Acoustic Architect + Sensor Integration

## Phase 1 Target: 2-Mic Spaced Pair
- Spacing: 17cm (approx human ear separation)
- ITD range: 0-500 microseconds
- ILD: 0-15dB depending on frequency
- CC27 (Spatial Confidence): ~80/127 at this tier

## Phase 2 Target: Full Binaural + Visual
- 2x MEMS mic + HRTF convolution
- Intel RealSense D435 (depth camera)
- 2x ultrasonic proximity (HC-SR04)
- Estimated budget: $200-300

## Open Questions
1. Minimum mic spacing for reliable ITD at speech frequencies (200-4000 Hz)?
2. HRTF database selection (MIT KEMAR vs. individual measured)?
3. Blind zone coverage: rear hemisphere without camera pivot?
4. Latency budget for real-time beamforming (<5ms target)?

## Reference Files
- INFOGRAPHIC - SPATIAL LOCALIZATION - Mono phantom sound source.jpg
- INFOGRAPHIC - Microphone Polar Patterns 01.jpg + 02.jpg
- binaural-article-fig1.jpg
- Impulse Response (IR) Measurement Techniques - JAES.pdf
