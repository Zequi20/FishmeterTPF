# Guía de uso de Fishmeter para los experimentos A, A′, B y C

## 1. Objetivo de esta guía

Esta guía explica cómo preparar, ejecutar y documentar cada experimento con la
interfaz gráfica de Fishmeter. Está dirigida a una persona que conoce el
montaje físico, pero no necesariamente la teoría de visión por computadora.

Fishmeter compara cuatro maneras de convertir puntos de una fotografía en
medidas físicas:

| Experimento | Referencia métrica | Corrección aplicada | Limitación principal |
|---|---|---|---|
| A | ArUco fijado al vidrio | Escala uniforme aproximada | El marcador y el pez están en planos distintos |
| A′ | ArUco coplanar con la réplica | Homografía del plano | Solo es válida dentro del plano del marcador |
| B | Damero sumergido, cámara y rail | Cámara pinhole efectiva bajo agua | La refracción queda absorbida solo de forma aproximada |
| C | Calibración en aire, puerto y plano físico | Trazado aire–vidrio–agua con Snell | Depende de medir correctamente la geometría física |

Los cuatro métodos usan los mismos puntos anatómicos y el mismo eje
longitudinal. Lo que cambia es la conversión de píxeles a milímetros. Una
diferencia entre métodos es un resultado posible del experimento; no debe
forzarse que los cuatro valores coincidan.

> **Importante:** el programa ayuda a marcar una sección perpendicular, pero no
> reconoce el pez, no excluye aletas y no encuentra automáticamente la máxima
> profundidad corporal. La selección anatómica sigue siendo responsabilidad de
> la persona que realiza el ensayo.

## 2. Decisiones que deben fijarse antes de comenzar

Escriba estas decisiones en el protocolo del estudio y no las cambie entre
réplicas:

1. **Convención de p1:** por ejemplo, punta más anterior visible del hocico.
2. **Convención de p2:** longitud total, longitud a la horquilla, longitud
   estándar u otra. La misma convención debe usarse en las fotografías y en la
   medición física de referencia.
3. **Región para la profundidad:** indique qué parte del cuerpo se examinará y
   cómo se excluirán las aletas.
4. **Origen del eje longitudinal:** alineación mecánica verificada, medición
   manual independiente u otro procedimiento. No use automáticamente la línea
   p1–p2 como eje.
5. **Tolerancia angular de p3–p4:** el valor inicial de la interfaz es 5°. Es un
   umbral operativo, no una constante biológica, y debe justificarse.
6. **Criterios de validación:** error absoluto máximo en mm, error porcentual
   máximo, o ambos.
7. **Condiciones constantes:** cámara, foco, zoom, resolución, orientación del
   vidrio, nivel de agua e iluminación.

Asigne además identificadores estables a cada réplica, repetición, patrón de
validación, perfil de calibración y posición del rail.

## 3. Instalación y apertura

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m fish_morphometry
```

También puede iniciar la aplicación con:

```bash
fish-morphometry
```

La ventana puede abrir sin imágenes ni calibraciones. Los datos experimentales
no vienen incluidos: deben ser aportados por el usuario.

Una organización práctica, no obligatoria, es:

```text
data/raw/          fotografías originales sin editar
data/annotations/  archivos JSON de p1–p4
calibrations/      perfiles y referencias geométricas
results/           resultados y validaciones exportados por el programa
```

No sobrescriba las fotografías originales. Use nombres que relacionen especie
o modelo, réplica, repetición, método y posición, por ejemplo
`replica_03_rep_02_z150.png`.

Los selectores de archivos de la aplicación comparten y conservan la última
carpeta utilizada, incluso después de cerrar y volver a abrir Fishmeter. Esto
incluye cargar imágenes, seleccionar varias vistas de calibración y guardar
perfiles o resultados. Si la carpeta ya no está disponible, el diálogo utiliza
su ubicación normal.

## 4. Flujo común: imagen, eje y puntos anatómicos

### 4.1 Campos y controles comunes

| Campo o control | Qué significa | Cómo completarlo |
|---|---|---|
| **Cargar imagen** | Fotografía que se va a medir | Use la imagen original. Al cargar otra imagen se borran los puntos, marcadores y resultados actuales, pero los perfiles de B/C permanecen cargados |
| **Diccionario** | Familia de códigos a la que pertenecen los ArUco | Debe coincidir con el diccionario usado al generar los marcadores. Solo afecta A y A′ |
| **Detectar ArUco** | Busca todos los marcadores del diccionario elegido | Necesario para A y A′; B y C no usan ArUco |
| **Cargar puntos JSON** | Recupera p1–p4 de una anotación anterior | El JSON debe corresponder a la misma imagen y resolución |
| **Guardar puntos JSON** | Guarda p1–p4 en píxeles de la imagen original | Úselo para aplicar exactamente la misma anotación en los cuatro métodos |
| **Seleccionar puntos manualmente** | Inicia la secuencia p1, p2, p3 y p4 | Defina antes el ángulo longitudinal correcto |
| **Marcar/remarcar profundidad** | Sustituye solo p3 y p4; conserva p1 y p2 | Úselo para probar otra sección corporal o después de cambiar el eje |
| **Guardar candidata** | Conserva una sección p3–p4 confirmada | Guarde varias secciones anatómicamente válidas para compararlas |
| **C1, C2, …** | Lista de secciones candidatas | Muestra la profundidad en píxeles y si la candidata corresponde a un eje anterior |
| **Usar candidata** | Convierte la candidata elegida en p3–p4 finales | La mayor cifra mostrada no se elige automáticamente |
| **Ángulo longitudinal en imagen (°)** | Dirección cabeza–cola en la imagen | 0° apunta a la derecha; 90° apunta hacia abajo porque Y crece hacia abajo. Puede usar valores negativos |
| **Tolerancia de sección p3–p4 (°)** | Desvío máximo permitido respecto de una perpendicular al eje | Debe estar entre 0° inclusive y 90° exclusivo. Justifique el valor en el protocolo |

Los campos de ángulo y tolerancia se comparten entre las pestañas. Cambiarlos en
una pestaña los cambia para A, A′, B y C.

### 4.2 Significado de los cuatro puntos

| Punto | Definición | Regla práctica |
|---|---|---|
| **p1** | Extremo anterior del hocico | Marque siempre la referencia anterior acordada |
| **p2** | Extremo posterior según la convención caudal | No cambie entre “cola total”, “horquilla” o “base caudal” durante el estudio |
| **p3** | Perfil dorsal de una sección candidata | Debe tocar el cuerpo y excluir la aleta si así lo define el protocolo |
| **p4** | Perfil ventral de la misma sección | Se restringe a la guía perpendicular que pasa por p3 |

La longitud informada no es necesariamente la diagonal p1–p2: el programa
proyecta la separación sobre el eje longitudinal. La profundidad se proyecta
sobre la normal a ese eje y solo se informa si la sección cumple la tolerancia.

### 4.3 Cómo marcar los puntos

1. Cargue la imagen.
2. Escriba el ángulo longitudinal real de la réplica.
3. Pulse **Seleccionar puntos manualmente**.
4. Marque p1 y después p2 según las convenciones ya acordadas.
5. Mueva el cursor a una sección candidata y marque p3 en el perfil dorsal.
6. Marque p4 en el perfil ventral. El programa lo restringirá a la guía
   perpendicular.
7. Revise ambos extremos y pulse **Confirmar sección** o `Enter`.
8. Si desea comparar otra zona, pulse **Guardar candidata**, luego
   **Marcar/remarcar profundidad** y repita los pasos 5–7.
9. Examine todas las candidatas y pulse **Usar candidata** sobre la sección que
   el protocolo determine como final.
10. Guarde los puntos en JSON.

Controles del visor:

- rueda del ratón o botones `+`/`−`: zoom;
- botón **Ajustar**: muestra la imagen completa;
- arrastre con botón derecho o central: desplaza la vista;
- arrastre de p3 o p4: ajusta un extremo sin salir de la guía;
- `Shift` + arrastre sobre p3/p4: mueve la sección completa; después deben
  revisarse ambos perfiles;
- flechas: ajustan el extremo activo un píxel;
- `Shift` + flechas: ajuste de 0,25 píxel;
- `Escape` o **Cancelar**: restaura los puntos anteriores.

Si cambia el ángulo longitudinal, Fishmeter conserva p3/p4 solo como referencia,
invalida los resultados y exige remarcarlos. No los mueve automáticamente.

### 4.4 Formato del JSON de puntos

```json
{
  "points_px": {
    "p1": [120.5, 310.0],
    "p2": [980.0, 326.5],
    "p3": [515.0, 240.0],
    "p4": [515.0, 415.0]
  }
}
```

Las coordenadas son píxeles de la imagen original, no del tamaño mostrado en
pantalla.

## 5. Experimento A: escala uniforme desde el vidrio

### 5.1 Qué se necesita

- un ArUco fijado a la cara interna del vidrio;
- su lado físico medido con calibre;
- el ID y diccionario usados para imprimirlo;
- la réplica visible en la misma fotografía;
- el eje y p1–p4 definidos según la sección 4.

El marcador debe estar plano, íntegro, nítido y sin reflejos fuertes. A es una
línea de base: trasladar la escala del vidrio al plano del pez es una
aproximación.

### 5.2 Campos de A

| Campo | Qué debe introducirse | Qué hace el programa |
|---|---|---|
| **Diccionario** | Familia exacta del ArUco | Permite decodificar el ID |
| **ID del ArUco** | Entero del marcador fijado al vidrio | Elige ese marcador entre todos los detectados |
| **Lado físico medido (mm)** | Longitud real de un lado, medida físicamente; debe ser positiva | Calcula una escala nominal `lado_mm / lado_medio_px` |
| **Ángulo longitudinal en imagen (°)** | Dirección cabeza–cola independiente de p1–p2 | Define el eje sobre el que se proyecta la longitud |
| **Tolerancia de sección p3–p4 (°)** | Máximo desvío admitido | Invalida la profundidad si la sección lo supera |

La interfaz usa además dos umbrales internos: lado medio mínimo de 30 px y
coeficiente de variación máximo de los cuatro lados de 0,10. Un marcador menor
se rechaza; una variación excesiva produce una advertencia. Estos valores no se
editan en la pantalla actual.

Los valores iniciales de la pantalla (`ID 10` y `30.0 mm`) son ejemplos. No los
use sin comprobar el marcador real.

### 5.3 Procedimiento

1. Monte el ArUco sobre el vidrio y mida su lado real.
2. Tome la fotografía sin cambiar la configuración de cámara del estudio.
3. Cargue la imagen, seleccione el diccionario y pulse **Detectar ArUco**.
4. Compruebe que la barra de estado muestre el ID esperado y un tamaño mayor que
   el mínimo.
5. Marque o cargue p1–p4 y confirme la sección final.
6. Abra **Método A**, escriba ID, lado físico, ángulo y tolerancia.
7. Pulse **Calcular A**.
8. Revise LT, profundidad, estado y advertencias.

### 5.4 Cómo interpretar A

- `total_length_mm`: longitud p1–p2 proyectada sobre el eje.
- `body_depth_mm`: profundidad p3–p4 si la sección es válida; `—`/nulo si no.
- `scale_mm_per_px`: escala uniforme usada por A.
- `WARNING` es esperable porque la propia implementación advierte que la escala
  del vidrio aproxima el plano del pez.

A no corrige explícitamente perspectiva, distorsión de lente ni refracción. No
describa el resultado como una medida ópticamente corregida.

## 6. Experimento A′: homografía de un marcador coplanar

### 6.1 Qué se necesita

- un ArUco rígidamente unido al soporte de la réplica;
- la cara impresa alineada con el plano de simetría de la réplica;
- su lado físico medido con calibre;
- una medición física del error de coplanaridad;
- el mismo p1–p4 y eje usados en A si se comparan ambos métodos.

No estime la coplanaridad mirando una sola fotografía. Mídala físicamente en el
montaje.

### 6.2 Campos de A′

| Campo | Qué debe introducirse | Qué hace el programa |
|---|---|---|
| **Diccionario** | Familia exacta del marcador coplanar | Permite detectarlo |
| **ID del ArUco** | Entero del marcador del soporte | Debe identificar al marcador coplanar, no al del vidrio |
| **Lado físico medido (mm)** | Lado real positivo | Define el cuadrado métrico de la homografía |
| **Error de coplanaridad (mm)** | Separación física no negativa entre el plano del marcador y el plano de simetría | Se registra para trazabilidad; no corrige la medición ni se propaga como incertidumbre |
| **Ángulo longitudinal en imagen (°)** | Mismo eje anatómico usado en los otros métodos | El eje también se transforma mediante la homografía |
| **Tolerancia de sección p3–p4 (°)** | Umbral angular acordado | Decide si se informa la profundidad |

El lado mínimo de 30 px y el coeficiente de variación máximo de 0,10 se aplican
igual que en A.

El valor inicial (`ID 11`, `30.0 mm`, error `0.0 mm`) es solo un ejemplo. Si A y
A′ aparecen en una misma imagen, use IDs distintos para evitar confundir sus
roles físicos.

### 6.3 Procedimiento

1. Alinee el ArUco con el plano de simetría de la réplica y mida cualquier
   separación residual.
2. Tome la fotografía y detecte los ArUco.
3. Use la misma anotación p1–p4 de A cuando la comparación corresponda a la
   misma imagen.
4. Abra **Método A′** y complete todos los campos.
5. Pulse **Calcular A′**.
6. Compare A′ con A en **Resultados**. La columna `A′ − A` conserva el signo:
   positivo significa que A′ produjo una medida mayor.

### 6.4 Cómo interpretar A′

A′ usa una homografía completa. El `scale_mm_per_px` exportado es solo una
referencia nominal y no una escala global. La homografía corrige perspectiva
dentro del plano coplanar, pero no corrige puntos fuera de ese plano,
distorsión residual ni una réplica curvada.

## 7. Experimento B: calibración pinhole efectiva bajo agua

### 7.1 Qué se necesita

- un damero rígido sumergible con geometría conocida;
- al menos 15 vistas utilizables para calibración, preferiblemente alrededor de
  20 o más para tolerar rechazos;
- al menos dos fotografías nuevas del damero en posiciones distintas del rail;
- posiciones del rail medidas en mm;
- el offset firmado entre el plano del tablero/soporte y el plano de simetría;
- una regla o barra sumergida para validación física.

B no usa el ArUco, aunque aparezca en la fotografía.

### 7.2 Parte 1: campos de calibración efectiva

| Campo o control | Significado | Cómo completarlo |
|---|---|---|
| **Cargar/importar perfil B** | Abre un perfil nativo B o un `calibration.yaml` pinhole de Calibmar | Al importar Calibmar debe escribir primero la posición de calibración, porque ese archivo no contiene el contexto del rail |
| **Crear con tablero…** | Ajusta un perfil nuevo con fotografías del damero sumergido | Complete antes todos los campos de esta parte |
| **Zona calibración (mm)** | Posición física `z_ref` del rail donde se tomó la calibración, idealmente la zona cercana al vidrio | Use el mismo origen y signo que en todas las posiciones posteriores |
| **Esquinas C×F** | Número de esquinas internas del damero: columnas y filas | No es el número de cuadrados. Cada valor debe ser al menos 2 |
| **Tamaño de cuadro (mm)** | Lado real de cada cuadrado del damero | Mídalo físicamente; debe ser positivo |
| **Calib. máx. px** | Error de reproyección máximo permitido por vista | Valor inicial 1,5 px. Las vistas que lo superan se rechazan iterativamente |
| **span** | Cobertura mínima de los centros del tablero como fracción de la imagen | Valor inicial 0,20; rango válido 0–1. Obliga a variar la ubicación del damero |
| **°** | Diversidad angular mínima del conjunto | Valor inicial 10°; rango válido 0–menos de 90°. Obliga a incluir inclinaciones distintas |

Todos los archivos de calibración deben tener la misma resolución. El perfil
guarda las vistas recibidas, aceptadas y rechazadas, sus motivos, RMS, errores,
centros, áreas e inclinaciones. Un RMS bajo indica consistencia del ajuste, no
exactitud física.

La detección intenta primero `findChessboardCornersSB` (flags 0, normalización y
normalización exhaustiva) y después el detector clásico con umbral adaptativo y
normalización. Solo el último aplica `cornerSubPix`; el log identifica el método
que aceptó cada fotografía y su tiempo aproximado.

Modelos Calibmar admitidos: `SIMPLE_PINHOLE`, `PINHOLE`, `SIMPLE_RADIAL`,
`RADIAL`, `OPENCV` y `FULL_OPENCV`. Un perfil `FLATPORT` corresponde a C y se
rechaza en B.

### 7.3 Cómo capturar y crear la calibración B

1. Mantenga fija la cámara, carcasa, vidrio, foco, zoom y resolución.
2. Coloque el damero sumergido aproximadamente en `z_ref`.
3. Tome al menos 15 vistas utilizables variando ubicación, tamaño aparente e
   inclinación. Cubra centro, laterales, parte superior e inferior.
4. Evite desenfoque, reflejos, tablero doblado o esquinas fuera de la imagen.
5. Complete los campos y pulse **Crear con tablero…**.
6. Seleccione todas las vistas. La calibración se ejecuta en segundo plano y la
   aplicación permanece utilizable. Revise **Log de calibración B** mientras se
   procesan: cada archivo queda marcado como aceptado o rechazado con su causa
   (imagen ilegible, resolución incompatible, tablero incompleto, fallo de
   refinamiento o error de reproyección). El mismo panel muestra las iteraciones
   de OpenCV, RMS, cobertura del encuadre y diversidad angular.
7. Guarde el perfil, por ejemplo `calibration_B.yaml`.
8. Registre el hash mostrado; identifica intrínsecos y resolución.

### 7.4 Parte 2: campos de referencia cámara–rail

| Campo o control | Significado | Cómo completarlo |
|---|---|---|
| **Cargar referencia rail** | Abre una referencia creada para el perfil B cargado | El hash del perfil y el contexto deben coincidir |
| **Crear referencia con solvePnP…** | Estima el plano del tablero y la dirección del rail | Requiere al menos dos fotos en posiciones distintas que abarquen `z_ref` |
| **Dirección estimada del rail x,y,z** | Vector unitario del rail en coordenadas de cámara | Es informativo y de solo lectura; lo estima el programa |
| **Sentido positivo** | Descripción textual de qué movimiento aumenta la posición | Ejemplo: `alejándose de la cámara`. Debe coincidir con los signos anotados |
| **rail ⟂ tablero** | Declara que el rail es perpendicular al tablero | Marque solo si el montaje lo verifica; el programa comprobará la coherencia |
| **planos de réplicas paralelos al tablero** | Declara el supuesto de paralelismo | Debe estar garantizado por el soporte físico y quedar marcado; B rechaza la medición si no fue confirmado |
| **Ref. máx. px** | Error máximo de reproyección de `solvePnP` | Valor inicial 1,0 px; debe ser positivo |
| **residuo mm** | Desviación máxima respecto del movimiento lineal del rail | Valor inicial 1,0 mm; debe ser positivo |
| **°** | Dispersión angular máxima entre normales de las distintas poses | Valor inicial 1,0°; debe estar entre 0° y 90° |

Para crearla:

1. Use el mismo damero y el perfil B ya cargado.
2. Tome fotografías nuevas en dos o más posiciones distintas. El intervalo debe
   incluir `z_ref`; por ejemplo, si `z_ref=100`, pueden usarse 80, 100 y 140 mm.
3. Pulse **Crear referencia con solvePnP…** y seleccione las fotos.
4. Cuando se solicite, escriba la posición física de cada foto en mm. La primera
   propone `z_ref`, pero puede corregirse.
5. Guarde `rail_reference_B.yaml`.

Con un tablero cuadrado, la textura no determina por sí sola el origen ni la
orientación de sus coordenadas. El programa advierte esta ambigüedad y no hace
inversiones automáticas; compruebe la orientación física o utilice una marca
asimétrica si la correspondencia entre posiciones es esencial.

No edite la dirección estimada a mano. Si el ajuste supera cualquiera de los
umbrales, revise posiciones, rigidez, detección o montaje.

La norma de escala pose/rail se informa aparte como diagnóstico. Si se aparta
más del 5 % de `1 mm/mm`, la referencia se guarda como **PROVISIONAL** para
pruebas piloto; no se corrige ni se reescala automáticamente. Los resultados B
siguen en `PENDING_VALIDATION` hasta registrar tramos conocidos en las
posiciones y regiones del encuadre utilizadas.

### 7.5 Parte 3: campos de captura y réplica

| Campo | Significado | Cómo completarlo |
|---|---|---|
| **Réplica** | Identificador obligatorio del objeto medido | Ejemplo: `R03`; no use nombres ambiguos |
| **Repetición** | Identificador opcional de repetición | Ejemplo: `2` o `rep02` |
| **Posición carrito (mm)** | Lectura física del rail al tomar la fotografía | Use exactamente el origen y sentido positivo de la referencia |
| **Offset simetría (mm)** | Desplazamiento firmado desde el plano de referencia hasta el plano de simetría | Mídalo físicamente. El signo sigue la dirección elegida en el campo siguiente |
| **Dirección del offset** | Eje sobre el que se aplica el offset | `rail`: a lo largo del rail; `plane_normal`: a lo largo de la normal del tablero/plano |
| **Eje imagen / tolerancia (°)** | Primer valor: ángulo longitudinal; segundo: tolerancia p3–p4 | Son los mismos campos compartidos con A/A′/C |
| **Máx. error validación (mm / %)** | Criterios de aceptación de una barra conocida | Puede dejar uno vacío; si completa ambos, deben cumplirse ambos. Sin ninguno, no se declara aprobación |

El offset no es una distancia absoluta: es un valor firmado. Documente con un
dibujo qué dirección se tomó como positiva.

### 7.6 Medir con B

1. Cargue el perfil B.
2. Cargue o cree la referencia cámara–rail correspondiente.
3. Cargue la fotografía de la réplica. No hace falta detectar ArUco.
4. Marque o cargue p1–p4 y confirme la profundidad.
5. Complete réplica, repetición, posición, offset, dirección, eje y tolerancia.
6. Pulse **Calcular B**.
7. Revise el resultado. Un cálculo geométricamente válido comienza como
   `PENDING_VALIDATION`; no es un error de operación.

`delta_rail_mm` es la posición de captura menos `z_ref`. No significa error: es
el desplazamiento usado para construir el plano de medición.

### 7.7 Validación física de B

La validación debe realizarse con una regla o barra sumergida colocada en el
mismo plano que se pretende medir:

1. Prepare tramos conocidos, por ejemplo 50 y 100 mm.
2. Capture el patrón en el centro y hacia los bordes, y en las posiciones del
   rail usadas por las réplicas.
3. Cargue una imagen de validación y marque p1/p2 en los extremos exactos del
   tramo. La pantalla exige también p3/p4 para habilitar el cálculo; complételos
   como una sección perpendicular, aunque la validación del tramo usa p1/p2.
4. Calcule B con la posición y offset reales del patrón.
5. Pulse **Registrar validación física…**.
6. Introduzca:
   - **Longitud real:** valor certificado o medido del tramo en mm;
   - **Ubicación:** use de forma consistente `center`, `left`, `right`, `top` o
     `bottom`;
   - **ID del patrón:** identificador estable, por ejemplo `barra_01`.
7. Revise error con signo, absoluto, porcentual y estado.

La validación se exporta a `results/b_physical_validation.json` y `.csv`. En la
GUI actual, el registro actualiza el resultado B que está abierto en ese
momento. Cargar otra imagen crea un resultado nuevo `PENDING_VALIDATION`; el
programa no promueve automáticamente todas las mediciones futuras a partir de
un archivo histórico. Conserve los archivos de validación como evidencia del
contexto experimental y no interprete `PENDING_VALIDATION` como `PASS`.

## 8. Experimento C: modelo refractivo aire–vidrio–agua

### 8.1 Convención geométrica

En C el origen es el centro de proyección de la cámara:

- X: hacia la derecha de la imagen;
- Y: hacia abajo;
- Z: desde la cámara hacia la pecera.

Todas las distancias geométricas internas están en mm. La normal del puerto debe
apuntar desde la cámara hacia la escena y, por tanto, tener componente Z
positiva.

C no usa ArUco ni una escala global mm/píxel. Tampoco puede reutilizar
automáticamente la pose cámara–rail de B: B y C trabajan en marcos físicos
distintos.

### 8.2 Parte 1: calibración en aire

| Campo o control | Significado | Cómo completarlo |
|---|---|---|
| **Cargar perfil aire** | Abre un perfil nativo de calibración en aire | Debe corresponder a la misma cámara, lente, foco, zoom y resolución |
| **Crear con tablero…** | Crea `K_air` y `D_air` con un damero fotografiado en aire | Requiere al menos 15 vistas utilizables |
| **Esquinas C×F** | Columnas y filas de esquinas internas | No use el número de cuadrados; mínimo 2×2 |
| **Tamaño** | Lado físico de cada cuadro | Debe ser positivo |
| **Unidad** | Unidad del tamaño escrito | Solo `mm`, `cm` o `m`; el programa normaliza a mm |

La pantalla de C usa para la calibración los umbrales internos 1,5 px por vista,
0,20 de cobertura mínima y 10° de diversidad, además de 15 vistas mínimas. La
GUI actual no expone esos tres umbrales para C.

Procedimiento:

1. Retire la cámara del medio acuático o use la configuración prevista para la
   calibración intrínseca en aire.
2. Mantenga foco, zoom y resolución idénticos a la medición.
3. Tome al menos 15 vistas utilizables del damero, con posiciones e
   inclinaciones variadas.
4. Complete esquinas, tamaño y unidad.
5. Pulse **Crear con tablero…** y seleccione las vistas. La calibración se
   ejecuta en segundo plano; la barra y el **Log de calibración C · aire**
   muestran el archivo procesado, detección, resolución, errores por vista,
   iteraciones de ajuste y comprobaciones de diversidad. La barra inferior solo
   conserva un resumen corto y no se utiliza para listar todos los rechazos.
6. Cuando el ajuste termine, guarde `calibration_C_air.yaml`. Si falla, revise
   el log desplazable dentro de la pestaña C; el diálogo final contiene solo un
   resumen para no ocultar ni bloquear la interfaz con una lista extensa.

La calibración en aire utiliza exactamente la misma secuencia de detección que
B, incluida la información del método y del tiempo de cada detección.

Un RMS menor que el objetivo del protocolo no valida por sí solo el método C.

### 8.3 Parte 2: puerto plano

Puede cargar un YAML manual, importar un perfil Calibmar `FLATPORT` o escribir
los valores en pantalla y pulsar **Aplicar puerto escrito**.

| Campo | Significado físico | Regla |
|---|---|---|
| **d interfaz (mm)** | Distancia desde el centro de proyección hasta la primera superficie aire–vidrio, medida sobre la normal | Debe ser positiva. No es, en general, la distancia desde el frente visible de la lente |
| **espesor (mm)** | Espesor del vidrio | Debe ser no negativo |
| **normal [x,y,z]** | Normal del puerto en el marco de cámara | El programa la normaliza; Z debe ser positiva. `[0,0,1]` representa un vidrio frontal paralelo al sensor |
| **n aire** | Índice de refracción del aire | Debe ser positivo; use el valor documentado para las condiciones del ensayo |
| **n vidrio** | Índice de refracción del vidrio | Debe provenir de la especificación o medición del material |
| **n agua** | Índice del agua | Depende de temperatura, salinidad y presión; registre esas condiciones |

Si solo conoce una distancia medida desde el frente de la lente, no la escriba
como si fuese una medida exacta desde el centro de proyección. Use un YAML con
`lens_distance_approximation: true` y una `uncertainty_note`.

Ejemplo de puerto manual:

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
  lens_distance_approximation: false
  uncertainty_note: null
  water_conditions:
    temperature_c: 22.0
    salinity_ppt: 0.0
    pressure_dbar: 0.0
```

Al importar Calibmar, el archivo debe declarar:

- un modelo pinhole compatible y sus `parameters`;
- `non_svp_model: FLATPORT`;
- `non_svp_parameters` en el orden
  `[Nx, Ny, Nz, int_dist, int_thick, na, ng, nw]`;
- `width` y `height` compatibles con la imagen;
- la unidad de `int_dist` e `int_thick`, mediante `units`, `non_svp_units` o el
  campo **Unidad** de la pestaña antes de importar.

Importar `FLATPORT` carga tanto la calibración de aire como el puerto.

### 8.4 Parte 3: plano de medición

El plano representa el plano de simetría de la réplica en el marco físico de la
cámara refractiva.

| Campo o control | Significado | Cómo completarlo |
|---|---|---|
| **Punto plano [x,y,z]** | Cualquier punto conocido perteneciente al plano, en mm | Debe medirse o calibrarse en `physical_camera_refractive` |
| **Normal plano [x,y,z]** | Vector perpendicular al plano | No puede ser nulo; el programa lo normaliza |
| **Usar plano explícito** | Construye el plano con los seis valores escritos | Use después de completar punto y normal |
| **Cargar plano YAML…** | Carga un plano documentado | Debe declarar mm y el marco físico correcto |

Ejemplo:

```yaml
measurement_plane:
  units: "mm"
  plane_id: "replica_plane_z300"
  source: "medicion_mecanica_2026-10-07"
  coordinate_frame: "physical_camera_refractive"
  point_camera_mm: [0.0, 0.0, 300.0]
  normal_camera: [0.0, 0.0, 1.0]
```

No copie el punto y la normal de la referencia B. Deben obtenerse directamente
para C.

### 8.5 Parte 4: captura y validación

| Campo | Significado | Cómo completarlo |
|---|---|---|
| **Réplica** | ID obligatorio | Use el mismo esquema de identificación del resto del estudio |
| **Repetición** | ID opcional | Identifica capturas repetidas |
| **Posición rail (mm, opcional)** | Metadato de posición | Solo aporta trazabilidad; no mueve el plano C definido arriba |
| **Eje imagen / tolerancia (°)** | Ángulo longitudinal y tolerancia p3–p4 | Son los campos comunes |
| **Máx. error validación (mm / %)** | Umbrales para una barra conocida | Si se completan ambos, deben cumplirse ambos; deben ser positivos |
| **Sensibilidad…** | Evalúa cambios del resultado frente a perturbaciones | No modifica el perfil ni sustituye la validación física |

### 8.6 Medir con C

1. Cargue o cree el perfil de aire.
2. Importe o configure el puerto plano.
3. Cargue o configure el plano de medición.
4. Cargue una fotografía con la misma resolución del perfil.
5. Marque los mismos p1–p4 usados en los demás métodos.
6. Complete réplica, repetición opcional, eje y tolerancia.
7. Pulse **Calcular C**.
8. Revise LT, profundidad, advertencias y estado.

Los rayos físicamente imposibles, casi paralelos o situados detrás de una
interfaz/plano se rechazan. No se sustituyen por un valor aproximado silencioso.
Todo resultado C nuevo comienza `PENDING_VALIDATION`.

### 8.7 Validación física de C

1. Coloque una regla o barra conocida exactamente en el plano configurado.
2. Capture al menos el centro y dos ubicaciones adicionales entre `left`,
   `right`, `top` y `bottom`.
3. Repita en las posiciones del rail relevantes aunque la posición sea solo un
   metadato en C.
4. En cada imagen marque p1/p2 en los extremos del tramo. Complete p3/p4 para
   habilitar el cálculo; la validación usa p1/p2.
5. Calcule C y pulse **Registrar validación…**.
6. Escriba longitud real, una ubicación exacta de la lista e ID del patrón.

Un registro individual puede ser `PASS`, pero el protocolo C solo pasa a
`PASS` cuando todos los registros compatibles pasan y existe cobertura del
centro más al menos dos ubicaciones adicionales. Un solo `FAIL` hace fallar el
conjunto. Los archivos se guardan como
`results/c_physical_validation.json` y `.csv`.

Los registros se acumulan en memoria durante la sesión y se enlazan solo si
coinciden los hashes del perfil, contexto, puerto y plano. Al cargar otra imagen
se crea un resultado nuevo y la GUI no lo promueve automáticamente usando un
archivo histórico; conserve y analice las validaciones junto con los resultados
del mismo contexto.

### 8.8 Sensibilidad de C

Con perfil, puerto, plano y p1–p4 completos, **Sensibilidad…** genera
`results/<imagen>_C_sensitivity.json`. La herramienta prueba, por defecto:

- distancia a la interfaz ±20 %;
- índice del agua ±0,01;
- espesor del vidrio ±0,5 mm;
- normal del puerto ±1° en dos direcciones;
- posición del plano ±1 mm;
- normal del plano ±1° en dos direcciones;
- desviaciones estándar de Calibmar, si existen.

El archivo muestra cambios absolutos y relativos de LT y profundidad. Sirve para
detectar parámetros sensibles, pero no es una propagación completa de
incertidumbre ni una prueba de exactitud.

## 9. Resultados, estados y exportación

### 9.1 Estados

| Estado | Interpretación |
|---|---|
| `OK` | Cálculo directo sin advertencias; no equivale por sí solo a validación física |
| `WARNING` | Hay un resultado, pero existe una limitación o control que debe revisarse |
| `PENDING_VALIDATION` | B o C fue calculado, pero todavía no tiene evidencia física suficiente vinculada |
| `PASS` | El registro o protocolo vinculado cumplió los umbrales configurados |
| `FAIL` | Al menos un criterio de validación fue excedido |
| `ERROR` | No existe una medición utilizable; consulte `exclusion_reason` o las advertencias |

Una profundidad mostrada como `—` no vale cero: significa que p3–p4 fue
invalidado o que no pudo calcularse.

### 9.2 Campos principales exportados

| Campo | Interpretación |
|---|---|
| `total_length_mm` | Longitud p1–p2 proyectada sobre el eje longitudinal |
| `body_depth_mm` | Profundidad p3–p4 proyectada; puede ser nula |
| `body_depth_valid` | Indica si p3–p4 cumplió la tolerancia |
| `*_euclidean_mm` | Distancia recta auxiliar para diagnóstico; no sustituye la medida proyectada |
| `body_depth_section_offset_mm` | Componente longitudinal indeseada de p3–p4 |
| `body_depth_section_angle_degrees` | Desvío de la sección respecto de la perpendicular |
| `points_px` | Los cuatro puntos originales compartidos |
| `points_metric_mm` | Puntos transformados por A/A′ |
| `points_camera_mm` | Puntos reconstruidos por B/C |
| `quality_status` y `quality_warnings` | Estado científico y advertencias |
| `*_hash` | Identificadores reproducibles de calibración, contexto, rail, puerto, plano o validación |
| `exclusion_reason` | Motivo por el que B/C no produjo una medida |

Los JSON contienen más trazabilidad que el resumen visible. En C también
incluyen los rayos en aire, vidrio y agua y las intersecciones con las
interfaces.

### 9.3 Botón de exportación

Pulse **Exportar resultados (results/)** después de calcular:

- A y A′ deben existir juntos para exportar los métodos directos;
- B puede exportarse solo;
- C puede exportarse solo;
- si están disponibles, B y C se agregan a la exportación conjunta de A/A′.

Se generan archivos como:

```text
results/<imagen>_A.json
results/<imagen>_A_prime.json
results/<imagen>_B.json
results/<imagen>_C.json
results/master.csv
```

`master.csv` se reescribe con los resultados disponibles de la exportación
actual; no funciona como una base de datos acumulativa. Copie o consolide sus
filas mediante un procedimiento controlado si procesa muchas imágenes.

## 10. Lista de comprobación por fotografía

Antes de aceptar un resultado, confirme:

- [ ] La imagen corresponde a la réplica, repetición y posición anotadas.
- [ ] La resolución coincide con el perfil usado en B/C.
- [ ] p1 y p2 siguen la convención caudal del protocolo.
- [ ] p3 y p4 tocan el cuerpo, no las aletas, y pertenecen a la misma sección.
- [ ] El ángulo longitudinal se determinó de forma independiente de p1–p2.
- [ ] Se eligió manualmente la candidata final de profundidad.
- [ ] A usa el ID del marcador del vidrio y A′ el marcador coplanar.
- [ ] El lado de cada ArUco procede de una medición física.
- [ ] B usa perfil, referencia, posición, offset y sentido compatibles.
- [ ] C usa un puerto y plano medidos en el marco físico refractivo.
- [ ] Las advertencias y el estado se conservaron junto con la medida.
- [ ] Se guardaron los puntos JSON y los resultados antes de pasar a otra imagen.

## 11. Errores frecuentes

| Problema | Causa probable | Corrección |
|---|---|---|
| **Calcular A/A′ está deshabilitado** | Falta imagen, ArUco, alguno de p1–p4 o confirmación de profundidad | Complete el flujo común y detecte los marcadores |
| **Calcular B está deshabilitado** | Falta perfil, referencia, réplica, posición, offset o puntos | Lea el texto `Falta:` del panel y complete cada elemento |
| **Calcular C está deshabilitado** | Falta perfil, puerto, plano, réplica, puntos, mm o resolución compatible | Corrija la entrada indicada por el panel |
| **No se detecta el damero** | Orden C×F incorrecto, reflejo, desenfoque u oclusión | Verifique esquinas internas y repita la captura |
| **Perfil incompatible** | Cambió la resolución o pertenece a otra cámara/configuración | Use la resolución y configuración originales o vuelva a calibrar |
| **Referencia B rechazada** | Posiciones no distintas, no abarcan `z_ref`, rail no lineal o tablero no paralelo | Repita las fotografías y mida las posiciones |
| **Profundidad nula** | p3–p4 supera la tolerancia | Remarque la misma sección sobre la guía; no aumente el umbral solo para obtener un número |
| **C rechaza un rayo** | Normal invertida, plano detrás de la cámara, geometría paralela o parámetros no físicos | Revise el marco X/Y/Z, signos, unidades y mediciones físicas |
| **Validación queda pendiente** | No hay umbrales o, en C, falta cobertura espacial | Defina criterios antes del ensayo y complete todas las ubicaciones |
| **Cambiar el eje invalida candidatas** | Las secciones pertenecen a la perpendicular del eje anterior | Remarque p3/p4; el programa no las corrige automáticamente |

## 12. Qué debe archivarse para que otra persona pueda repetir el ensayo

Conserve juntos:

1. protocolo anatómico y convención caudal;
2. fotografías originales y tabla de réplica/repetición/posición;
3. JSON de p1–p4 por imagen;
4. diccionario, IDs, medidas físicas y ubicación de los ArUco;
5. imágenes de calibración y perfiles B/C guardados;
6. referencia cámara–rail B y posiciones usadas;
7. mediciones del puerto y plano C, con unidades e incertidumbres;
8. temperatura, salinidad y presión del agua cuando correspondan;
9. umbrales de calibración y validación;
10. JSON/CSV de resultados, validaciones y sensibilidad;
11. versión de Fishmeter y de OpenCV registrada en los perfiles;
12. fotografías o croquis del montaje y del sentido positivo del rail.

La reproducibilidad requiere conservar las entradas y advertencias, no solo las
columnas finales de longitud y profundidad.

## 13. Relación con `configs/experiment.example.yaml`

El archivo `configs/experiment.example.yaml` documenta una configuración de
A/A′ para uso programático mediante `fish_morphometry.config.load_config()`.
La interfaz gráfica actual **no tiene un botón para cargar ese archivo**. Por
eso, editar el YAML no cambia automáticamente los campos visibles: en la GUI
debe introducir los valores reales de nuevo.

Sus campos principales son:

| Campo YAML | Significado |
|---|---|
| `experiment.name` | Nombre del ensayo |
| `experiment.units` | Unidad declarada: mm, cm o m |
| `aruco.dictionary` | Diccionario de ambos marcadores |
| `aruco.method_a.id` / `side_mm` | ID y lado físico del marcador del vidrio |
| `aruco.method_a.role` | Debe ser `glass` |
| `aruco.method_a.plane` | Debe ser `glass_inner_surface` |
| `aruco.method_a_prime.id` / `side_mm` | ID y lado del marcador coplanar |
| `aruco.method_a_prime.role` | Debe ser `coplanar` |
| `aruco.method_a_prime.plane` | Debe ser `replica_symmetry_plane` |
| `coplanarity_error_mm` | Error físico de coplanaridad de A′ |
| `measurements.longitudinal_axis_px` | Vector del eje, equivalente al ángulo de la GUI |
| `measurements.maximum_depth_section_angle_degrees` | Tolerancia angular de p3–p4 |
| `quality.minimum_marker_side_px` | Lado observado mínimo aceptado |
| `quality.maximum_side_cv` | Variación relativa máxima recomendada entre lados |

Las secciones comentadas de B y C son una plantilla documental; el flujo de la
GUI carga sus perfiles, referencias, puerto y plano desde los controles
descritos en esta guía. Sustituya siempre los números del ejemplo por mediciones
del montaje real.
