# Verificación analítica del módulo refractivo de puerto plano (método C)

## Objetivo

Verificar que el trazado refractivo de C (`trace_refracted_ray`) y la medición
completa (`measure_c`) reproducen la solución analítica de la ley de Snell para
dos interfaces planas y paralelas aire–vidrio–agua, con incidencia oblicua,
índices distintos en cada medio y vidrio de espesor no nulo.

Las pruebas anteriores del módulo cubrían casos sin refracción efectiva
(µ = 1, t_g = 0, incidencia normal o una sola interfaz) y un valor de regresión
calculado por el mismo código. En esta verificación, los valores esperados se
calculan dentro del archivo de pruebas con trigonometría escalar, de forma
independiente del código de Fishmeter:

```text
sen θa · µa = sen θg · µg = sen θw · µw
r(θa, z) = d · tan θa + t_g · tan θg + z · tan θw
```

donde `r` es la distancia radial al eje óptico en un plano situado `z` mm
detrás de la cara interna del vidrio.

Parámetros del montaje de la tesis usados en todas las pruebas:
d = 230 mm, t_g = 4 mm, µa = 1,000, µg = 1,500 y µw = 1,333. La cámara
sintética tiene 4096 × 3072 px, fx = fy = 3000 px, centro principal en
(2048, 1536) y sin distorsión.

Es una verificación numérica de la implementación frente al modelo físico. No
sustituye la validación física con objetos de longitud conocida, y los resultados
de C siguen comenzando en `PENDING_VALIDATION`.

## Resultados

Archivo: [`tests/unit/test_refractive_analytic.py`](../tests/unit/test_refractive_analytic.py).
Los errores son los máximos absolutos medidos sobre todos los casos de cada
prueba en la ejecución que acompaña a la etiqueta `v1.1-tesis` (Python 3.12.3,
NumPy de `.venv`).

| Prueba | Casos | Entrada | Valor esperado y origen | Tolerancia | Error máximo medido |
|---|---|---|---|---|---|
| `test_trace_matches_analytic_flat_port` | 27 | θa = 5°, 20°, 35°; acimut = 0°, 30°, 135°; z = 50, 110, 230 mm; d, t_g y µ del montaje | Punto de intersección (x, y, z) según la fórmula analítica `r(θa, z)`; invariante `µ · sen θ` en los tres medios | 1×10⁻⁶ mm (punto); 1×10⁻¹² (invariante) | x, y: 2,8×10⁻¹⁴ mm; z: 0; `µ · sen θ`: 1,1×10⁻¹⁶ |
| `test_reference_value_for_thesis` | 1 | θa = 20°, acimut = 0°, z = 110 mm | x = 113,851166 mm (fórmula analítica; sin refracción serían 125,205761 mm) | 1×10⁻⁵ mm | 3,4×10⁻⁷ mm (respecto del valor redondeado a 6 decimales; frente a la fórmula sin redondear, 0) |
| `test_round_trip_known_point_behind_glass` | 4 | (x, y, z) = (40, 0, 110), (−60, 35, 50), (90, −70, 230), (0, 0, 170) mm | El mismo punto, tras resolver θa analíticamente (bisección sobre `r(θa, z)`) y trazarlo con Fishmeter | 1×10⁻⁶ mm | 1,4×10⁻¹⁴ mm |
| `test_measure_c_recovers_known_length` | 4 | Réplica sintética fuera del centro (centro en x = 60, y = 40 mm), LT = 140 mm, PC = 40 mm; z = 50, 110, 170, 230 mm | LT y PC conocidas; los píxeles de p1–p4 se obtienen por proyección analítica directa | Euclidianas: 1×10⁻⁶ mm; proyectadas: 1×10⁻⁴ mm | LT euclidiana: 2,8×10⁻¹⁴ mm; PC euclidiana: 3,6×10⁻¹⁴ mm; LT proyectada: 1,7×10⁻⁵ mm; PC proyectada: 4,9×10⁻⁶ mm |
| `test_wrong_depth_changes_length_as_first_order_model_predicts` | 1 | Réplica a z real = 110 mm medida con plano supuesto a z = 170 mm | LT > 140 mm y LT ≈ 140 · D(170)/D(110), con D(z) = d + t_g/µg + z/µw (ecuación 16 de la tesis) | 1 % relativo | LT = 159,4545 mm frente a 159,9931 mm predichos (−0,34 %) |

Notas sobre los resultados:

- En las pruebas 1 a 4 las diferencias son del orden del error de redondeo en
  doble precisión.
- En la prueba 4, LT y PC proyectadas usan el eje horizontal de la imagen, que
  `measure_c` traza con un punto auxiliar desplazado 1 px. Al transformarlo al
  plano de medición, el eje gira levemente respecto del segmento real, y esa
  diferencia (≤ 1,7×10⁻⁵ mm) no se debe a un error del trazado refractivo.
- En la prueba 5, la diferencia del 0,34 % corresponde al modelo de primer
  orden (paraxial) de la ecuación 16, no al trazado exacto: la réplica está
  fuera del eje, con ángulos de incidencia en aire de hasta unos 24°.

## Reproducción

Desde la raíz del repositorio, con el entorno virtual del proyecto:

```bash
.venv/bin/pytest tests/unit/test_refractive_analytic.py -v
```

Resultado esperado: `37 passed`.

## Alcance

Las pruebas no modifican el algoritmo; los resultados de la tesis obtenidos con
v1.0-tesis son idénticos con v1.1-tesis. Entre ambas etiquetas no hay cambios en
`src/` (`git diff v1.0-tesis v1.1-tesis --stat -- src/` está vacío); solo se
agregan este documento, el archivo de pruebas y una referencia en `README.md`.
