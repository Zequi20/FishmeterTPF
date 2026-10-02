# Fish Morphometry

Aplicación de escritorio para medir réplicas de peces con los métodos A y A′ mediante una escala métrica directa obtenida de un marcador ArUco. Esta entrega permite cargar imágenes, detectar marcadores, cargar o seleccionar cuatro puntos anatómicos, calcular longitud total y profundidad corporal, comparar ambos métodos y exportar sus resultados.

Los métodos B, C y Calibmar siguen deshabilitados. No se implementan corrección refractiva, ley de Snell, calibración pinhole, homografías, reconstrucción 3D, segmentación neuronal ni análisis estadístico.

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

La aplicación no requiere imágenes, puntos, configuraciones ni calibraciones para abrirse. La configuración YAML se carga explícitamente desde código o desde futuras pantallas; el arranque no depende de ella.

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
6. Revisa la tabla comparativa y exporta cuando ambos métodos estén calculados.

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
├── io/exporters.py                JSON y CSV
└── ui/                            Tkinter/ttk, imagen y resultados
tests/                             Pruebas unitarias sintéticas
```
