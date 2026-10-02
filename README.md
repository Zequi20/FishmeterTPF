# Fish Morphometry

Base ejecutable para gestionar un experimento de medición morfométrica de peces mediante los métodos A, A′, B y C. Esta primera entrega contiene únicamente la estructura del proyecto y una pantalla principal informativa; **todavía no mide peces ni procesa imágenes**.

## Requisitos

- Python 3.11 o superior.
- En Ubuntu, el soporte de Tkinter se instala con:

  ```bash
  sudo apt install python3-tk
  ```

- Las dependencias Python (NumPy, OpenCV y PyYAML) se declaran en `pyproject.toml`.

## Instalación y arranque

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m fish_morphometry
```

También queda disponible el comando instalado:

```bash
fish-morphometry
```

La ventana abre sin imágenes, calibraciones, parámetros físicos ni una instalación de Calibmar. El archivo `configs/experiment.example.yaml` es una plantilla documental y no se carga durante el arranque.

## Estructura

```text
configs/                  Configuraciones de ejemplo
data/raw/                 Imágenes originales (futuro)
data/annotations/         Puntos y anotaciones (futuro)
data/references/          Referencias físicas (futuro)
calibrations/air/         Calibraciones en aire (futuro)
calibrations/water_pinhole/ Calibraciones pinhole bajo agua (futuro)
calibrations/flatport/    Parámetros FLATPORT (futuro)
results/                  Resultados generados (futuro)
src/fish_morphometry/     Código de la aplicación
tests/                    Pruebas automatizadas
```

Los algoritmos se incorporarán más adelante en estos módulos:

- `src/fish_morphometry/methods/a.py`: escala mediante ArUco fijado al vidrio.
- `src/fish_morphometry/methods/a_prime.py`: escala mediante ArUco coplanar con la réplica.
- `src/fish_morphometry/methods/b.py`: cámara pinhole calibrada bajo agua e intersección futura con el plano del pez.
- `src/fish_morphometry/methods/c.py`: modelo refractivo aire–vidrio–agua e intersección futura con el plano del pez.

La interfaz vive en `src/fish_morphometry/ui/`; `app.py` centralizará el arranque y el manejo de errores de inicio.

## Estado actual y límites

La pantalla principal es una guía visual de preparación. Los botones visibles están deshabilitados porque las acciones se habilitarán en etapas posteriores. No se implementan detección de ArUco, calibraciones, lectura de Calibmar, segmentación, marcado de puntos, escalado, trazado de rayos, ley de Snell, mediciones, análisis estadístico ni gráficos experimentales.

