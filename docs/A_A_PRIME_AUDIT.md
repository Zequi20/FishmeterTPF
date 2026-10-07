# Auditoría teórica de A y A′

Esta nota aplica las secciones 3, 5, 7, 9, 10, 12 y 14 de
`MORFOMETRIA_CONTEXTO_CODEX.md` a la implementación actual.

## Resultado inicial

La implementación anterior de ambos métodos estaba en
`src/fish_morphometry/methods/_direct.py` y usaba:

```text
k = lado_físico_mm / lado_observado_px
medida = ||p_b - p_a||₂ · k
```

Por lo tanto:

- **A** usa correctamente un marcador cuyo rol queda registrado como
  `glass`/`glass_inner_surface` y calcula la misma escala directa para los dos
  pares de puntos.
- **A′** usa correctamente un marcador cuyo rol queda registrado como
  `coplanar`/`replica_symmetry_plane` y conserva `coplanarity_error_mm` como
  dato físico externo, sin inferirlo de una imagen monocular.
- Ambos métodos reciben los mismos `p1`–`p4`, tal como exige la comparación
  controlada.
- Las pruebas existentes solo demostraban los casos alineados.

## Concordancia y límite de la concordancia

La distancia euclidiana coincide con la longitud longitudinal teórica

```text
L = |(q2 - q1) · u|
```

solo cuando `q2-q1` es paralelo al eje anatómico `u` (o cuando la definición
experimental pide explícitamente la distancia de segmento). También coincide
con la profundidad si `p3` y `p4` pertenecen a la misma sección perpendicular.

En consecuencia, las mediciones de los fixtures iniciales concordaban
numéricamente con la teoría **bajo la condición de pez alineado, escala
uniforme y p3–p4 en una misma sección**. Esos casos no demostraban que el código
fuera válido para una imagen rotada, perspectiva apreciable, escalas distintas
en x/y o p3–p4 seleccionados en estaciones diferentes.

Caso normativo de la especificación:

```text
q1=(0,0), q2=(4,4), u=(1,0)
proyección longitudinal = 4
distancia euclidiana    = 5.656854...
```

El cálculo anterior devolvía `5.656854... · k`, no `4 · k`. Esto identificó una
incompatibilidad teórica aunque los fixtures alineados pasaran.

## Interpretación por método

En A, el ArUco está en el vidrio y no acompaña el plano de la réplica. La escala
directa es una aproximación; separación de planos, inclinación y perspectiva
pueden introducir error. Una discrepancia A–B/C no puede atribuirse solo a
refracción.

En A′, la coplanaridad reduce el error de profundidad y es el control directo
apropiado. La homografía admite perspectiva planar, aunque una vista extrema,
la distorsión de lente o una coplanaridad imperfecta todavía pueden degradar el
resultado. `coplanarity_error_mm` se registra, pero no se propaga como
incertidumbre.

## Corrección aplicada

La implementación corregida:

- recibe un eje longitudinal explícito en coordenadas de imagen;
- transforma los puntos antes de medir;
- usa escala uniforme aproximada para A y homografía coplanar para A′;
- transforma también el eje al espacio métrico de A′;
- calcula p1–p2 por proyección sobre `u`;
- calcula p3–p4 por proyección sobre `n`;
- invalida la profundidad si p3–p4 excede la tolerancia angular configurable;
- conserva puntos métricos, ejes, distancias euclidianas y error de sección;
- marca A con una advertencia explícita por la diferencia entre el plano del
  vidrio y el plano del pez.

La corrección no elimina la limitación física de A ni decide automáticamente la
convención caudal de p2. El valor inicial de tolerancia es operativo y debe
justificarse para el montaje experimental.
