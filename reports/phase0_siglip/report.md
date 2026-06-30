# Phase 0 scoring harness report

- generated_at: 2026-06-29T02:23:41.888005+00:00
- model_version: `siglip:google/siglip-base-patch16-224:fp32`
- template_set_id: `drawing_v1`
- raw formula: `Cy * (1 - Cx)`, hard-zeroed on OCR attack

## Tau 100

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.0625 | 0.0723 | 0.1357 | confused | false | 1.3146 |
| apple_baseball_poor | medium | 0.1011 | 0.1162 | 0.1302 | confused | false | 1.3031 |
| apple_baseball_good | strong | 0.5158 | 0.5503 | 0.0626 | fooled | false | 1.2664 |
| apple_baseball_text_attack | attack | 0.0000 | 0.3107 | 0.0763 | failed | true | 1.4922 |

- raw spread: `0.5158`
- mean entropy: `1.3441`

## Tau 50

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.1063 | 0.1292 | 0.1770 | confused | false | 1.5407 |
| apple_baseball_poor | medium | 0.1357 | 0.1642 | 0.1738 | confused | false | 1.5392 |
| apple_baseball_good | strong | 0.3179 | 0.3621 | 0.1222 | failed | false | 1.5219 |
| apple_baseball_text_attack | attack | 0.0000 | 0.2573 | 0.1275 | failed | true | 1.5753 |

- raw spread: `0.3179`
- mean entropy: `1.5443`

## Tau 30

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.1268 | 0.1564 | 0.1889 | confused | false | 1.5862 |
| apple_baseball_poor | medium | 0.1468 | 0.1806 | 0.1868 | confused | false | 1.5859 |
| apple_baseball_good | strong | 0.2473 | 0.2916 | 0.1519 | confused | false | 1.5787 |
| apple_baseball_text_attack | attack | 0.0000 | 0.2346 | 0.1539 | failed | true | 1.5965 |

- raw spread: `0.2473`
- mean entropy: `1.5868`

## Tau 20

| case | expected | raw | Cy | Cx | bucket | ocr | entropy |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| apple_plain | weak | 0.1376 | 0.1706 | 0.1935 | confused | false | 1.5995 |
| apple_baseball_poor | medium | 0.1517 | 0.1878 | 0.1921 | confused | false | 1.5994 |
| apple_baseball_good | strong | 0.2155 | 0.2589 | 0.1676 | confused | false | 1.5961 |
| apple_baseball_text_attack | attack | 0.0000 | 0.2231 | 0.1685 | failed | true | 1.6036 |

- raw spread: `0.2155`
- mean entropy: `1.5996`

## Phase 0 questions

- Q1 spread check at tau 30: strong-minus-weak raw delta = `0.1204`.
- Q2 text attack check: OCR hard-zero passed = `true`.
- Q3 tau smoothness check: mean entropy by tau = 100:1.3441, 50:1.5443, 30:1.5868, 20:1.5996.
- Gate: `go` for this dataset/model run.

- non_attack_cases: `3`
