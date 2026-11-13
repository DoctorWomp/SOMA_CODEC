# Buffer Size / Latency Reference
**Filed:** 2026-07-07 | **Role:** Optimization Engineer

## Latency Math
`Latency (ms) = (Buffer Size / Sample Rate) * 1000`

## Full Table @ 44.1kHz
| Buffer | Latency | CPU | Use Case |
|--------|---------|-----|----------|
| 64     | 1.45ms  | Max | Hard RT instruments only |
| 128    | 2.9ms   | High | Pro audio mixing |
| 256    | 5.8ms   | Medium-High | DAW recording |
| 512    | 11.6ms  | Medium | ✅ SOMA CODEC primary target |
| 1024   | 23.2ms  | Low-Medium | ✅ SOMA CODEC safe default |
| 2048   | 46.4ms  | Low | Validation/file-mode |
| 4096   | 92.9ms  | Very Low | Batch analysis |

## Human Perception Reference
| Event | Approx Time | Notes |
|-------|-------------|-------|
| Fastest conscious reaction | ~200ms | Startle reflex faster (~80ms) |
| Audible echo threshold | ~20ms | Below = no echo perceived |
| Lip sync tolerance | ~45ms | Film/video standard |
| Conversational pause | ~250ms | Natural gap between speakers |

**Conclusion:** 23ms (1024 buffer) is imperceptible in conversation.
512 buffer gives headroom for future latency-sensitive features.

## CDC Mode Buffer Switching
Different situational tiers can use different buffer sizes:
| CDC Mode | Recommended Buffer | Rationale |
|----------|-------------------|----------|
| IDLE | 2048 | Low CPU, full analysis |
| STANDARD | 1024 | Conversational |
| ALERT | 512 | Faster response |
| DEFENSE | 512 | Maximum responsiveness |
| EMERGENCY | 256 | Maximum speed, higher CPU |
