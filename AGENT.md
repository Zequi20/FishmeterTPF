# Guía para agentes de desarrollo

## Alcance

Este archivo aplica a todo el repositorio Fishmeter. Su objetivo es orientar a
agentes que analicen o modifiquen el proyecto sin alterar las definiciones
morfométricas, las convenciones experimentales ni la trazabilidad de los
resultados.

Antes de modificar código, revisar:

1. `README.md`, que describe el flujo operativo vigente.
2. `docs/MORFOMETRIA_CONTEXTO_CODEX.md`, especificación técnica y teórica.
3. `Teoría.md`, material de base para la tesis; no debe tratarse como redacción
   final ni como sustituto de evidencia experimental.
4. Las auditorías específicas de `docs/`, especialmente
   `A_A_PRIME_AUDIT.md` y `METODO_B_CORRECCIONES.md`.
5. El estado actual del repositorio y los cambios no confirmados del usuario.

Si una solicitud contradice la teoría documentada, no adaptar silenciosamente
las ecuaciones. Explicar la contradicción y conservar una implementación
físicamente interpretable.

## Propósito del proyecto

Fishmeter es una aplicación de escritorio en Python/Tkinter para medir réplicas
de peces mediante cuatro tratamientos experimentales:

- **A:** escala uniforme aproximada a partir de un ArUco fijado al vidrio.
- **A′:** transformación por homografía mediante un ArUco coplanar con la
  réplica.
- **B:** reconstrucción con una calibración pinhole efectiva obtenida en agua y
  una referencia geométrica cámara–rail.
- **C:** trazado refractivo explícito aire–vidrio–agua y posterior intersección
  con el plano de medición.

El proyecto compara métodos; no debe forzarse que produzcan el mismo resultado.
Las diferencias pueden ser parte del experimento.

## Reglas científicas obligatorias

### Puntos anatómicos compartidos

- `p1`: extremo anterior del hocico.
- `p2`: extremo posterior definido por la convención caudal del protocolo.
- `p3`: punto dorsal de la sección corporal elegida manualmente.
- `p4`: punto ventral de la misma sección.
- A, A′, B y C deben usar el mismo conjunto original `p1`–`p4` para una
  comparación controlada.
- Los puntos del visor se guardan en coordenadas de la imagen original, nunca en
  coordenadas de pantalla.
- No mover, regenerar ni remarcar puntos automáticamente para un método
  particular.

### Eje y medidas proyectadas

El eje longitudinal unitario `u` es una entrada explícita. No debe deducirse de
`p3–p4`, y tampoco debe sustituirse automáticamente por la dirección `p1–p2`.
La normal dorsoventral es `n = (-u_y, u_x)` en el plano 2D correspondiente.

Las medidas principales son proyecciones:

```text
LT = abs(dot(q2 - q1, u))
PC = abs(dot(q4 - q3, n))
```

- Los puntos `q` y los ejes deben pertenecer al mismo espacio geométrico.
- Las distancias euclidianas se conservan como diagnóstico, no como reemplazo
  de las proyecciones longitudinal y dorsoventral.
- `p3–p4` debe pertenecer a una sección perpendicular a `u`. Si excede la
  tolerancia, la profundidad se invalida; no se proyectan puntos desalineados y
  se presenta el valor como si fuese una sección aceptada.
- Un cambio del eje invalida o exige revisar `p3–p4`. No corregir puntos antiguos
  de manera silenciosa.

### Selección manual de profundidad

La guía visual solo restringe geométricamente la marcación. No detecta perfiles,
no excluye aletas y no demuestra que la sección sea el máximo global.

- El usuario decide la anatomía, compara candidatas y confirma la sección
  final.
- Describir el resultado como **profundidad máxima seleccionada manualmente**.
- No presentarlo como un máximo verificado automáticamente.
- Mantener separadas la selección anatómica, la conversión métrica y la
  corrección óptica.
- No incorporar segmentación, contornos o selección automática salvo solicitud
  explícita y actualización del protocolo.

### Interpretación de A y A′

- A usa la escala del plano del vidrio. Es una aproximación cuando el pez no es
  coplanar con el marcador; la separación entre planos y la refracción no quedan
  corregidas por una escala uniforme.
- A′ usa una homografía del plano coplanar. La homografía no corrige objetos
  fuera de ese plano, distorsión residual de lente ni errores de coplanaridad.
- `coplanarity_error_mm` es un dato físico externo. No inferirlo de una imagen
  monocular.
- El campo `scale_mm_per_px` de A′ es nominal; la medición debe emplear la
  homografía completa.

### Interpretación de B

- B no utiliza ArUco para medir, aunque exista uno en la imagen.
- `K_B` y `D_B` representan una calibración pinhole efectiva a través del medio.
  `D_B` no es una corrección física explícita de refracción.
- Conservar posiciones del rail, offsets firmados, planos, ejes, resolución y
  hashes de calibración/referencia.
- No declarar exactitud a partir del RMS de calibración.
- Los resultados comienzan en `PENDING_VALIDATION` y requieren validación física
  en las posiciones y regiones realmente utilizadas.

### Interpretación de C

- C usa intrínsecos en aire, dos refracciones de Snell y un plano de medición
  expresado en el marco físico de la cámara refractiva.
- Convención de cámara: `X` derecha, `Y` abajo y `Z` desde la cámara hacia la
  pecera. El centro de proyección es el origen.
- La distancia a la interfaz se mide desde el centro de proyección. Una medida
  desde el frente de la lente solo puede usarse como aproximación documentada.
- Las unidades geométricas internas son milímetros.
- No reutilizar automáticamente en C el plano cámara–rail estimado para B.
- Rechazar rayos o geometrías físicamente imposibles; no sustituirlos por
  valores aproximados silenciosos.
- C también comienza en `PENDING_VALIDATION`. El RMS o una simulación de
  sensibilidad no sustituyen la validación física.

## Arquitectura del código

```text
src/fish_morphometry/
├── calibration/   perfiles de cámara e importadores Calibmar
├── domain/        modelos serializables y nombres canónicos
├── geometry/      rayos, planos, Snell, puerto plano y rail
├── io/            exportación JSON/CSV
├── measurements/  puntos, escala, morfometría y guía de profundidad
├── methods/       orquestación de A, A′, B y C
├── ui/            interfaz Tkinter y visor
├── validation/    validación física y sensibilidad
└── vision/        detección y control de calidad ArUco
```

Mantener la geometría numérica en funciones puras fuera de la interfaz. La UI
debe coordinar el flujo y representar el estado, no duplicar ecuaciones de los
módulos de medición o geometría.

## Contratos de datos y errores

- Usar los modelos de `domain/models.py` para resultados trazables.
- Conservar compatibilidad con JSON/CSV existentes. Los cambios de exportación
  deben ser aditivos cuando sea posible y deben probarse.
- No eliminar diagnósticos, hashes, unidades, ejes, puntos transformados ni
  motivos de exclusión.
- Usar `MeasurementError` para entradas o geometrías inválidas esperables.
- Usar `QualityReport` para estados y advertencias que formen parte del
  resultado científico.
- No producir datos ficticios para completar calibraciones o validaciones.
- No incluir imágenes, calibraciones privadas ni resultados experimentales en
  el repositorio. Las rutas de datos indicadas en `.gitignore` son locales.

## Convenciones de implementación

- Python 3.11 o superior, anotaciones de tipo y `dataclass` donde corresponda.
- Mantener nombres de API y campos serializados en inglés; textos de interfaz,
  documentación y errores orientados al usuario en español.
- Validar dimensiones, finitud, unidades y compatibilidad de resolución antes
  de realizar operaciones geométricas.
- Preferir funciones pequeñas y deterministas para transformaciones, vectores y
  proyecciones.
- No capturar excepciones genéricas para ocultar un error geométrico.
- Preservar cambios no relacionados que ya existan en el árbol de trabajo.
- Actualizar documentación cuando cambie una convención científica o el flujo de
  usuario.

## Instalación y ejecución

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m fish_morphometry
```

La aplicación debe poder iniciar sin imágenes, calibraciones ni configuraciones
experimentales cargadas.

## Pruebas obligatorias

Ejecutar, como mínimo:

```bash
.venv/bin/python -m compileall -q src tests
.venv/bin/pytest -q
.venv/bin/pytest --cov=src/fish_morphometry --cov-report=term-missing -q
```

La cobertura global no debe quedar por debajo de 70 %.

Para cambios geométricos, incluir casos:

- nominal y rotado;
- horizontal e inclinado;
- entradas nulas, degeneradas, no finitas o fuera de rango;
- transformación entre espacios de coordenadas;
- invariancia esperada ante traslación/rotación cuando corresponda;
- rechazo explícito de geometrías físicamente imposibles.

Para cambios del visor, mantener pruebas lógicas sin display y, cuando haya un
servidor gráfico disponible, comprobar que la ventana se construye y que zoom,
desplazamiento, confirmación y cancelación preservan coordenadas originales.

## Criterio de finalización

Un cambio está terminado cuando:

1. respeta las definiciones anatómicas y el espacio geométrico de cada método;
2. no aumenta implícitamente el alcance científico ni afirma una validación no
   realizada;
3. conserva la correspondencia de puntos y la trazabilidad de entradas;
4. tiene pruebas proporcionales al riesgo y pasa la suite completa;
5. mantiene la cobertura mínima;
6. actualiza documentación y exportaciones si cambia un contrato observable;
7. informa con claridad qué decisiones continúan dependiendo del usuario o del
   protocolo experimental.
