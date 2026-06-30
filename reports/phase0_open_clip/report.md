# Phase 0 scoring harness report

- generated_at: 2026-06-29T02:20:43.178489+00:00
- model_version: `open_clip:ViT-L-14:openai:fp32`
- template_set_id: `drawing_v1`
- raw formula: `Cy * (1 - Cx)`, hard-zeroed on OCR attack

## Tau 100

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0000 | 0.0002 | 0.9899 | failed | false | 0.0626 |
| apple_baseball_poor | medium | 0.0066 | 0.0527 | 0.8741 | failed | false | 0.4783 |
| apple_baseball_good | strong | 0.9987 | 0.9989 | 0.0002 | fooled | false | 0.0094 |
| apple_baseball_text_attack | attack | 0.0000 | 0.9996 | 0.0000 | failed | true | 0.0035 |

- raw spread: `0.9987`
- mean entropy: `0.1385`

## Tau 50

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0016 | 0.0113 | 0.8621 | failed | false | 0.5557 |
| apple_baseball_poor | medium | 0.0577 | 0.1529 | 0.6226 | failed | false | 1.0625 |
| apple_baseball_good | strong | 0.9355 | 0.9474 | 0.0125 | fooled | false | 0.2684 |
| apple_baseball_text_attack | attack | 0.0000 | 0.9729 | 0.0036 | failed | true | 0.1506 |

- raw spread: `0.9355`
- mean entropy: `0.5093`

## Tau 30

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0169 | 0.0480 | 0.6480 | failed | false | 1.1017 |
| apple_baseball_poor | medium | 0.1069 | 0.1979 | 0.4595 | failed | false | 1.3535 |
| apple_baseball_good | strong | 0.7295 | 0.7742 | 0.0577 | fooled | false | 0.8280 |
| apple_baseball_text_attack | attack | 0.0000 | 0.8463 | 0.0295 | failed | true | 0.6144 |

- raw spread: `0.7295`
- mean entropy: `0.9744`

## Tau 20

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0441 | 0.0867 | 0.4917 | failed | false | 1.3754 |
| apple_baseball_poor | medium | 0.1329 | 0.2109 | 0.3699 | failed | false | 1.4822 |
| apple_baseball_good | strong | 0.5312 | 0.5936 | 0.1052 | fooled | false | 1.2229 |
| apple_baseball_text_attack | attack | 0.0000 | 0.6718 | 0.0718 | failed | true | 1.0597 |

- raw spread: `0.5312`
- mean entropy: `1.2851`

## Phase 0 questions

- Q1 spread check at tau 30: strong-minus-weak raw delta = `0.7126`.
- Q2 text attack check: OCR hard-zero passed = `true`.
- Q3 tau smoothness check: mean entropy by tau = 100:0.1385, 50:0.5093, 30:0.9744, 20:1.2851.
- Gate: `go` for this dataset/model run.

- non_attack_cases: `3`
