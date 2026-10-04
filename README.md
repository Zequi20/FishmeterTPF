# Fish Morphometry

Aplicación de escritorio para medir réplicas de peces con los métodos A, A′, B y C. A y A′ conservan la escala métrica directa obtenida de un marcador ArUco. B usa un tablero rígido sumergido para ajustar una cámara pinhole efectiva convencional. C calibra la cámara en aire y modela explícitamente el puerto plano aire–vidrio–agua mediante dos refracciones de Snell.

B y C no utilizan el tamaño, la pose ni la escala de ningún ArUco, aunque un marcador aparezca en la fotografía. B es una aproximación pinhole efectiva a través de agua y vidrio: `D_B` solo modela la distorsión del ajuste y no es una corrección física de la refracción. C usa `K_air`, `D_air`, la ley de Snell y los parámetros medidos del puerto plano; por eso ambos métodos deben validarse con una regla o barra sumergida.

## Requisitos e instalación en Ubuntu

Se requiere Python 3.11 o superior, Tkinter y las dependencias Python declaradas en `pyproject.toml` (NumPy, `opencv-contrib-python` y PyYAML). En Ubuntu:

```bash
sudo apt update
sudo apt install python3.12-venv python3-tk
```

Si la distribución usa otro paquete de versión, puede instalar `python3-venv` en lugar de `python3.12-venv`.

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Si ya existe un `.venv` incompleto porque faltaba `ensurepip`, elimínelo y créelo de nuevo después de instalar `python3.12-venv`:

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
```

## Ejecución y pruebas

Con el entorno activado:

```bash
python -m fish_morphometry
python -m unittest discover -s tests -v
```

También se instala el lanzador:

```bash
fish-morphometry
```

La aplicación no requiere imágenes, puntos, configuraciones ni calibraciones para abrirse. La configuración YAML de A/A′ se carga explícitamente desde código; los perfiles y referencias de B se cargan desde su panel y el arranque no depende de ellos.

## Flujo de A y A′

1. **Cargar imagen**: selecciona una imagen BGR compatible con OpenCV.
2. **Detectar ArUco**: elige el diccionario, detecta todos los marcadores visibles y muestra ID, lado medio en píxeles y estado de detección.
3. **Cargar puntos JSON** o **Seleccionar puntos manualmente**. Después de seleccionar los cuatro puntos puede usar **Guardar puntos JSON**. Los cuatro puntos son:
   - `p1`: extremo anterior del hocico.
   - `p2`: extremo posterior de la réplica.
   - `p3`: extremo superior de la profundidad corporal máxima.
   - `p4`: extremo inferior de la profundidad corporal máxima.
4. Introduce el lado físico medido con calibre para el marcador de A y A′.
5. Calcula A y/o A′. Ambos reciben exactamente el mismo diccionario de puntos.
6. Para B, carga o crea el perfil de calibración, carga o crea la referencia cámara–rail, introduce el ID de réplica, posición del carrito y desplazamiento físico hasta el plano de simetría. El botón de B permanece deshabilitado si falta cualquiera de esos datos.
7. Para C, abre su pestaña, carga un perfil de calibración en aire o crea uno con al menos 15 vistas, importa un YAML Calibmar `FLATPORT` o un `flat_port` manual, y define el plano de simetría explícito o desde la geometría del rail de B. El cálculo permanece `PENDING_VALIDATION` hasta validar físicamente el modelo.
8. Revisa la tabla comparativa y exporta. El CSV maestro incluye A, A′, B y C cuando están disponibles; cualquiera de B o C puede exportarse por separado.

El selector manual convierte los clics desde la imagen redimensionada a coordenadas de la imagen original antes de guardar o calcular.

## Definición experimental

El método A usa un ArUco fijado a la cara interna del vidrio (`marker_role: glass`, `marker_plane: glass_inner_surface`). El marcador no acompaña espacialmente a la réplica.

El método A′ usa un ArUco instalado en el soporte del carrito, con la cara impresa alineada con el plano de simetría de la réplica (`marker_role: coplanar`, `marker_plane: replica_symmetry_plane`). El campo `coplanarity_error_mm` registra una medición física; la aplicación no intenta inferirla desde una imagen monocular.

Para ambos métodos se usa:

```text
k = lado_físico_mm / lado_observado_px
distancia_mm = distancia_euclidiana_px × k
```

El lado observado es la media de los cuatro lados detectados del cuadrado ArUco. No se usa el tamaño nominal del diccionario. El lado físico debe medirse con calibre.

## Calidad y limitaciones

La aplicación produce `ERROR` cuando no puede calcular de forma válida: imagen ilegible, marcador ausente, ID incorrecto, lado físico inválido, marcador demasiado pequeño, puntos faltantes/repetidos o coordenadas fuera de imagen.

Produce `WARNING` cuando el cálculo es posible pero el coeficiente de variación de los cuatro lados del ArUco supera el umbral configurado. Las advertencias se conservan en la tabla, JSON y CSV; ninguna captura se descarta silenciosamente.

La escala directa supone que la geometría observada es suficientemente representativa. Perspectiva, inclinación del marcador, distancia entre el plano del marcador de vidrio y el plano de la réplica y falta de coplanaridad pueden introducir error. Esta versión no corrige esos efectos.

## Método B: procedimiento reproducible

1. **Calibración efectiva en la zona cercana al vidrio.** Prepare un tablero rígido y mida físicamente el lado de cada cuadro en mm. En la pantalla B indique las esquinas internas (columnas × filas), el tamaño medido, la resolución y la posición `z_ref_mm` del rail. Recoja al menos 15 vistas utilizables (preferiblemente unas 20 o más), con inclinaciones y ubicaciones variadas dentro del encuadre, manteniendo el tablero aproximadamente en esa zona. Se refinan las esquinas con `cornerSubPix` y se ajusta `cv2.calibrateCameraExtended`. El perfil guarda vistas recibidas/aceptadas/rechazadas y su causa, RMS y error por vista. Un RMS menor de 0,7 px es un objetivo de la guía, no una declaración de exactitud.

   También se puede cargar el `calibration.yaml` raíz de Calibmar con `model`, `parameters`, `width` y `height`. Esta versión documenta y soporta los modelos pinhole `SIMPLE_PINHOLE`, `PINHOLE`, `SIMPLE_RADIAL`, `RADIAL`, `OPENCV` y `FULL_OPENCV`, adaptando el orden de parámetros a `K_B,D_B` de OpenCV. Rechaza perfiles con `non_svp_model: FLATPORT` y modelos fisheye.

2. **Referencia cámara–rail.** Coloque el tablero en `z_ref_mm`, con su superficie donde estaría el plano de simetría, y tome una fotografía nueva con la cámara fija. El botón de referencia detecta/refina el tablero y ejecuta `cv2.solvePnP`; se guardan el punto y la normal del plano en cámara, la dirección unitaria y el sentido positivo del rail, `z_ref_mm`, la pose y el error de reproyección. La fotografía de referencia no se sustituye por una pose inclinada de la calibración. Si se declara que el rail es perpendicular al tablero, la dirección se valida; también debe confirmarse explícitamente que los planos de las réplicas permanecen paralelos. Sin esos datos el cálculo queda bloqueado.

3. **Medición.** Para cada fotografía se registran el ID de imagen, réplica, repetición, posición del carrito y offset físico hasta el plano de simetría. B ejecuta `cv2.undistortPoints(points, K_B, D_B, P=None)`, interpreta cada `(x,y)` como el rayo efectivo `(x,y,1)`, construye el plano trasladado por `delta_z_mm = z_captura_mm − z_ref_mm` y calcula la intersección general rayo–plano. Devuelve `LT_B_mm = ||p2−p1||` y `PC_B_mm = ||p4−p3||`, las cuatro coordenadas 3D efectivas, calidad, advertencias, hash del perfil y referencia usada. Las mediciones fuera de la zona de calibración se marcan con advertencia y deben validarse físicamente.

4. **Comprobación física.** Sumerja una regla o barra en el plano de la réplica y registre tramos conocidos de 50 y 100 mm (si están disponibles), en el centro y hacia los bordes del encuadre, en la zona de calibración y en las demás posiciones del rail. En la GUI puede usar p1/p2 para los extremos del tramo y «Registrar validación física». `results/b_physical_validation.csv` y `.json` guardan valor real, estimado, error con signo, error absoluto, error porcentual, posición, `delta_z_mm`, ubicación, hash y referencia. No se generan datos ficticios ni se infiere exactitud desde el RMS.

## Método C: puerto plano explícito

C recibe exactamente el mismo conjunto de puntos `p1`–`p4` anotado para A, A′ y B. No vuelve a segmentar la imagen, no calcula una escala global `mm/píxel` y no consulta ArUco. El resultado es:

```text
LT_C_mm = ||P2 - P1||
PC_C_mm = ||P4 - P3||
```

La convención de cámara es `X` hacia la derecha de la imagen, `Y` hacia abajo y `Z` desde la cámara hacia la pecera. El centro de proyección es el origen. El puerto usa las interfaces paralelas `n·X = d` y `n·X = d + t_g`, donde `d` es la distancia desde el centro de proyección a la primera interfaz y `t_g` es el espesor del vidrio. Una distancia medida desde el frente de la lente no debe introducirse como `d` salvo que se marque expresamente como aproximación (`lens_distance_approximation`) y se documente su incertidumbre.

### Calibración en aire

En la pestaña C se seleccionan imágenes del tablero, esquinas internas, tamaño físico y unidad (`mm`, `cm` o `m`). Se refinan las esquinas con `cornerSubPix` y se ejecuta `cv2.calibrateCameraExtended`. El perfil guarda `K_air`, `D_air`, resolución, `rvec`/`tvec` y error por vista, RMS global, fecha, versión de OpenCV, imágenes aceptadas/rechazadas y hash. Se solicitan como mínimo 15 vistas (preferiblemente unas 20); RMS menor que 0,5 px es solo un objetivo de referencia y nunca declara válido C por sí mismo.

### Calibmar FLATPORT

Se acepta un YAML con `model`, `parameters`, `non_svp_model: FLATPORT`, `non_svp_parameters: [Nx, Ny, Nz, int_dist, int_thick, na, ng, nw]`, `width` y `height`. `OPENCV`, `FULL_OPENCV`, `PINHOLE`, `SIMPLE_PINHOLE`, `RADIAL` y `SIMPLE_RADIAL` se convierten a `K_air,D_air`. La unidad de `int_dist` e `int_thick` debe declararse explícitamente (no se asume mm); todos los valores geométricos se normalizan internamente a mm. Se rechazan perfiles sin `FLATPORT` y resoluciones incompatibles. Una normal no unitaria se normaliza y el ajuste queda registrado.

La alternativa manual es:

```yaml
flat_port:
  units: "mm"
  normal_camera: [0.0, 0.0, 1.0]
  interface_distance_mm: 200.0
  glass_thickness_mm: 4.0
  refractive_indices:
    air: 1.000
    glass: 1.500
    water: 1.333
```

También puede cargarse un plano desde:

```yaml
measurement_plane:
  point_camera_mm: [0.0, 0.0, 300.0]
  normal_camera: [0.0, 0.0, 1.0]
```

### Trazado y calidad

Cada píxel se undistorsiona con `K_air,D_air`, se convierte en `v_air` unitario, se intersecta con la primera interfaz (`q1`), se refracta a `v_glass`, avanza hasta `q2`, se refracta a `v_water` y se intersecta con el plano de medición. Se rechazan rayos paralelos o detrás de una interfaz/plano, normales inválidas, valores no finitos y reflexión interna total. Se conservan `q1`, `q2`, `v_air`, `v_glass`, `v_water`, puntos finales, plano, parámetros físicos y residuos de interfaz para depuración. C empieza siempre con `PENDING_VALIDATION`; una captura imposible queda `ERROR` con su motivo.

Puede reutilizarse el plano cámara–rail ya construido para B, pero C vuelve a trazar el rayo refractado y no reutiliza el rayo pinhole de B. La tabla de resultados compara A, A′, B y C; los JSON individuales y `results/master.csv` incluyen la misma trazabilidad.

### Validación física y sensibilidad

Antes de comparar peces, sumerja una regla o barra con marcas conocidas (10 mm; tramos de 50/100 mm), mida en el centro y laterales del encuadre y repita en varias posiciones del rail. «Registrar validación» guarda `valor_real_mm`, `valor_estimado_mm`, error con signo, absoluto y porcentual, posición del rail, ubicación, perfil y hash en `results/c_physical_validation.json/.csv`. El criterio inicial es error absoluto ≤ 1 %; si no se cumple, el resultado queda pendiente y deben revisarse la geometría, `d`, espesor, índices y plano.

La herramienta «Sensibilidad…» varía en memoria `d` ±20 %, `n_water` ±0,01, espesor y normal ±1° y exporta el cambio en LT/PC. Nunca modifica el perfil guardado. Las limitaciones conocidas son profundidad del plano, inclinación del puerto, incertidumbre de `d`, índices dependientes de temperatura y cualquier desviación del vidrio respecto a un plano paralelo.

## Configuración

`configs/experiment.example.yaml` contiene un ejemplo para A/A′:

```yaml
experiment:
  name: "A_A_prime_pilot"
  units: "mm"
aruco:
  dictionary: "DICT_4X4_50"
  method_a:
    id: 10
    side_mm: 30.0
    role: "glass"
    plane: "glass_inner_surface"
  method_a_prime:
    id: 11
    side_mm: 30.0
    role: "coplanar"
    plane: "replica_symmetry_plane"
    coplanarity_error_mm: 0.0
quality:
  minimum_marker_side_px: 30
  maximum_side_cv: 0.10
```

La función `fish_morphometry.config.load_config()` valida y convierte este archivo a modelos tipados. Los valores físicos del ejemplo deben sustituirse por las mediciones reales del montaje.

## Estructura principal

```text
configs/experiment.example.yaml
data/raw/                         Imágenes originales
data/annotations/                 Puntos y anotaciones
data/results/                     Resultados asociados a datos (futuro)
results/                          JSON y CSV exportados
src/fish_morphometry/
├── config.py                     Configuración YAML
├── domain/models.py               Modelos de marcadores y resultados
├── vision/aruco_detector.py      Detección y métricas ArUco
├── measurements/
│   ├── direct_scale.py            Escala y distancias
│   ├── points.py                  JSON y validación de p1–p4
│   └── quality.py                 Errores y advertencias
├── methods/a.py                   Método A
├── methods/a_prime.py             Método A′
├── methods/b.py                   Método B (pinhole efectivo y rayos)
├── calibration/                   Calibración B, aire e importadores Calibmar
├── geometry/                      Referencia rail, Snell, puerto y rayo–plano
├── validation/                    Validación física B y C; sensibilidad
├── io/exporters.py                JSON y CSV
└── ui/                            Tkinter/ttk, imagen y resultados
tests/                             Pruebas unitarias sintéticas A/A′/B/C
```

Las pruebas se ejecutan con:

```bash
python -m unittest discover -s tests -v
```
