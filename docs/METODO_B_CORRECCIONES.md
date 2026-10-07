# Correcciones teóricas y operativas del método B

Este documento registra las decisiones aplicadas al método B a partir de las
secciones 3–9 y 11–14 de `MORFOMETRIA_CONTEXTO_CODEX.md`. No reemplaza el
protocolo anatómico de la especie ni convierte el modelo pinhole efectivo en un
modelo refractivo.

## Definición de las medidas

Los puntos originales `p1`–`p4` se retroproyectan con `K_B,D_B` y se
intersectan con el plano métrico de la réplica. El eje longitudinal indicado en
la imagen también se transforma a ese plano y se normaliza como `u`. La normal
dorsoventral `n` pertenece al mismo plano.

```text
LT_B = abs(dot(P2 - P1, u))
PC_B = abs(dot(P4 - P3, n))
```

`PC_B` solo se informa cuando el ángulo de la componente longitudinal de
`P4-P3` no supera la tolerancia configurada. Si la supera, el campo queda nulo,
`body_depth_valid=false` y se conserva la distancia euclidiana como diagnóstico.
La diagonal euclidiana de `P2-P1` tampoco sustituye la longitud proyectada.

El eje no se deduce de `p1-p2`, porque eso haría que la proyección volviera a
ser equivalente a la diagonal. Debe provenir de la alineación verificada del
montaje o de una estimación anatómica independiente.

## Geometría cámara–rail

La dirección del rail se estima con el tablero observado en dos o más
posiciones físicas distintas que abarquen `z_ref_mm`. El ajuste verifica:

- error de reproyección de cada pose;
- residuo métrico de la trayectoria lineal del tablero;
- coherencia angular de las normales del tablero;
- escala del desplazamiento observado respecto del desplazamiento del rail.

El offset al plano de simetría tiene una dirección explícita: `rail` o
`plane_normal`. `delta_z_mm` se conserva por compatibilidad en los archivos,
pero su nombre inequívoco es `delta_rail_mm`.

## Calibración y trazabilidad

La calibración elimina iterativamente vistas cuyo error individual excede el
umbral y exige diversidad espacial y angular configurable. El hash óptico
identifica `K_B,D_B`, modelo y resolución. Un segundo hash identifica el contexto
experimental, incluida la posición de calibración. La referencia del rail posee
su propio hash y enlaza ambos.

## Estado de validación

Un resultado B nuevo queda `PENDING_VALIDATION`. El RMS o encontrarse en
`delta_rail_mm=0` no demuestran exactitud. Una barra de longitud conocida genera
`PASS` o `FAIL` solamente al compararse con los umbrales configurados. El
registro solo puede asociarse al resultado si coinciden perfil, contexto,
referencia, posición y offset.

## Limitación restante

B sigue siendo una aproximación pinhole efectiva calibrada a través de la
interfaz. Su validez debe comprobarse en las posiciones y zonas del encuadre del
experimento. El tratamiento físico de la refracción aire–vidrio–agua corresponde
al método C.
