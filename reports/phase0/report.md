# Phase 0 scoring harness report

- generated_at: 2026-06-29T02:02:40.066032+00:00
- model_version: `heuristic-color-shape-v1`
- template_set_id: `drawing_v1`
- raw formula: `Cy * (1 - Cx)`, hard-zeroed on OCR attack

Note: this run uses the deterministic heuristic judge. It validates the harness, OCR guard, and tau sweep only. Real go/no-go still requires OpenCLIP/SigLIP model runs.

## Tau 100

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0000 | 0.0000 | 0.4364 | failed | false | 0.6850 |
| apple_baseball_poor | medium | 0.0336 | 0.0886 | 0.6206 | failed | false | 0.8699 |
| apple_baseball_good | strong | 1.0000 | 1.0000 | 0.0000 | fooled | false | 0.0000 |
| apple_baseball_text_attack | attack | 0.0000 | 1.0000 | 0.0000 | failed | true | 0.0000 |

- raw spread: `1.0000`
- mean entropy: `0.3887`

## Tau 50

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0000 | 0.0000 | 0.4681 | failed | false | 0.6911 |
| apple_baseball_poor | medium | 0.0944 | 0.1832 | 0.4849 | failed | false | 1.0281 |
| apple_baseball_good | strong | 1.0000 | 1.0000 | 0.0000 | fooled | false | 0.0000 |
| apple_baseball_text_attack | attack | 0.0000 | 1.0000 | 0.0000 | failed | true | 0.0000 |

- raw spread: `1.0000`
- mean entropy: `0.4298`

## Tau 30

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0000 | 0.0000 | 0.4808 | failed | false | 0.6926 |
| apple_baseball_poor | medium | 0.1362 | 0.2366 | 0.4244 | failed | false | 1.0787 |
| apple_baseball_good | strong | 1.0000 | 1.0000 | 0.0000 | fooled | false | 0.0001 |
| apple_baseball_text_attack | attack | 0.0000 | 1.0000 | 0.0000 | failed | true | 0.0001 |

- raw spread: `1.0000`
- mean entropy: `0.4429`

## Tau 20

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0000 | 0.0000 | 0.4870 | failed | false | 0.6969 |
| apple_baseball_poor | medium | 0.1613 | 0.2649 | 0.3910 | confused | false | 1.1298 |
| apple_baseball_good | strong | 0.9992 | 0.9993 | 0.0002 | fooled | false | 0.0065 |
| apple_baseball_text_attack | attack | 0.0000 | 0.9994 | 0.0001 | failed | true | 0.0060 |

- raw spread: `0.9992`
- mean entropy: `0.4598`

## Phase 0 questions

- Q1 spread check at tau 30: strong-minus-weak raw delta = `1.0000`.
- Q2 text attack check: OCR hard-zero passed = `true`.
- Q3 tau smoothness check: mean entropy by tau = 100:0.3887, 50:0.4298, 30:0.4429, 20:0.4598.
- Gate: `not decided`. The offline heuristic run cannot prove the game; it only proves the harness is ready for real model scoring.

- non_attack_cases: `3`
