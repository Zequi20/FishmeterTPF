# Base teórica de los experimentos A, A′, B y C

## Propósito y alcance

Este documento resume la teoría que justifica las funciones principales del
software de morfometría. Está pensado como material de trabajo para redactar
posteriormente el capítulo metodológico de la tesis. No es una redacción final
ni sustituye la descripción del montaje experimental, el protocolo anatómico o
el análisis estadístico.

El análisis se realizó sobre la implementación actual de `Fishmeter` y sobre el
contexto técnico de `MORFOMETRIA_CONTEXTO_CODEX.md`. La idea central del sistema
es comparar cuatro maneras de convertir observaciones de una imagen en medidas
físicas:

- **A:** escala uniforme obtenida de un marcador situado sobre el vidrio.
- **A′:** transformación proyectiva obtenida de un marcador coplanar con la
  réplica del pez.
- **B:** cámara pinhole efectiva calibrada bajo agua, seguida de la
  intersección de rayos con un plano conocido.
- **C:** cámara calibrada en aire y trazado físico del rayo a través de las
  interfaces aire–vidrio–agua.

Los cuatro métodos comparten los mismos puntos anatómicos y la misma definición
de las medidas. Lo que cambia entre ellos es la transformación desde el píxel
hasta el espacio métrico.

---

## 1. Definiciones morfométricas comunes

### 1.1 Puntos anatómicos

La implementación usa cuatro puntos:

- \(p_1\): extremo anterior del hocico;
- \(p_2\): extremo posterior correspondiente a la convención caudal elegida;
- \(p_3\): extremo dorsal de la sección corporal seleccionada;
- \(p_4\): extremo ventral de esa misma sección.

La FAO señala que una medición de longitud debe indicar con precisión qué punto
anterior, qué extremo caudal y qué disposición de la aleta se emplearon. Por
eso, \(p_2\) no puede definirse solamente como “el último píxel del pez”. La
convención puede corresponder, por ejemplo, a longitud total, longitud a la
horquilla o longitud estándar, pero debe ser la misma en la referencia física,
la anotación de imágenes y los resultados [1].

La profundidad corporal debe medir el cuerpo y no la extensión de las aletas.
Además, \(p_3\) y \(p_4\) deben pertenecer a una misma sección, aproximadamente
perpendicular al eje cabeza–cola.

### 1.2 Espacios de coordenadas

Conviene distinguir los siguientes espacios:

- píxeles de la imagen original;
- coordenadas sin distorsión de lente;
- coordenadas rectificadas de un plano;
- coordenadas métricas en milímetros;
- coordenadas tridimensionales obtenidas mediante el modelo pinhole o el modelo
  refractivo.

Una regla importante es que los puntos y los ejes usados para medir deben estar
expresados en el mismo espacio. Si los puntos se transforman, también debe
transformarse el eje anatómico. Esta condición explica por qué A′, B y C no
reutilizan directamente el eje en píxeles después de convertir los puntos.

### 1.3 Eje longitudinal y eje dorsoventral

En dos dimensiones, sea el eje longitudinal unitario

\[
\mathbf{u}=(u_x,u_y), \qquad \|\mathbf{u}\|=1.
\]

Su normal dentro del plano es

\[
\mathbf{n}=(-u_y,u_x).
\]

En B y C las coordenadas métricas son tridimensionales, aunque todos los puntos
medidos están restringidos a un plano. Si \(\mathbf{s}\) es la normal de ese
plano, el eje longitudinal se proyecta primero sobre él:

\[
\widetilde{\mathbf{u}}
=\mathbf{u}_0-(\mathbf{u}_0\cdot\mathbf{s})\mathbf{s},
\qquad
\mathbf{u}=\frac{\widetilde{\mathbf{u}}}
{\|\widetilde{\mathbf{u}}\|}.
\]

El eje dorsoventral dentro del plano se obtiene con el producto vectorial:

\[
\mathbf{n}=\frac{\mathbf{s}\times\mathbf{u}}
{\|\mathbf{s}\times\mathbf{u}\|}.
\]

Estas operaciones están implementadas en `normalize_axis`,
`measure_projected_morphometry` y `measure_projected_morphometry_3d`, dentro de
`src/fish_morphometry/measurements/morphometry.py`.

### 1.4 Longitud total proyectada

Después de transformar los puntos a un espacio métrico, la longitud utilizada
por el programa es

\[
L_T=\left|(\mathbf{q}_2-\mathbf{q}_1)\cdot\mathbf{u}\right|.
\]

Esta fórmula mide la separación longitudinal entre dos perpendiculares al eje
del pez. No es necesariamente igual a la distancia directa entre los puntos:

\[
d_E=\|\mathbf{q}_2-\mathbf{q}_1\|_2.
\]

Por ejemplo, si \(\mathbf{q}_2-\mathbf{q}_1=(4,4)\) y
\(\mathbf{u}=(1,0)\), la longitud longitudinal es 4, mientras que la distancia
euclidiana es aproximadamente 5,657. La implementación conserva la distancia
euclidiana como diagnóstico, pero no la usa como sustituto de la longitud
proyectada.

No se calcula \(\mathbf{u}\) automáticamente como la dirección entre \(p_1\) y
\(p_2\). Si se hiciera, la proyección volvería a ser igual a la distancia
euclidiana y se perdería la diferencia entre una longitud axial y un segmento
diagonal. El eje debe proceder de la alineación controlada del montaje o de una
estimación anatómica independiente.

### 1.5 Profundidad corporal proyectada

La profundidad se calcula como

\[
P_C=\left|(\mathbf{q}_4-\mathbf{q}_3)\cdot\mathbf{n}\right|.
\]

Para comprobar si ambos puntos pertenecen aproximadamente a la misma sección,
se calcula también el desplazamiento longitudinal

\[
e_s=\left|(\mathbf{q}_4-\mathbf{q}_3)\cdot\mathbf{u}\right|
\]

y el ángulo de desalineación

\[
\alpha=\operatorname{atan2}(e_s,P_C).
\]

La profundidad solo se informa cuando \(\alpha\) no supera la tolerancia
configurada. De lo contrario, el programa conserva los diagnósticos pero asigna
un valor nulo a la profundidad corporal. La tolerancia inicial de 5 grados es
una decisión operativa del software, no una constante biológica universal. En
la tesis debe justificarse a partir del error admisible y del protocolo de
anotación.

### 1.6 Funciones compartidas

| Función | Fundamento | Uso |
|---|---|---|
| `validate_points` | Comprueba que los datos geométricos sean completos y finitos | A, A′, B y C |
| `normalize_axis` | Convierte el eje anatómico en un vector unitario | A, A′, B y C |
| `measure_projected_morphometry` | Proyecciones sobre ejes anatómicos en un plano 2D | A y A′ |
| `measure_projected_morphometry_3d` | Proyecciones sobre ejes contenidos en un plano 3D | B y C |

---

## 2. Experimento A: escala uniforme desde el vidrio

### 2.1 Objetivo del método

El experimento A representa el procedimiento más simple. Un marcador ArUco de
lado físico conocido está fijado a la cara interna del vidrio. La imagen permite
estimar cuántos milímetros representa, aproximadamente, un píxel.

La detección ArUco devuelve el identificador y las cuatro esquinas del marcador.
Este tipo de marcador está diseñado para ser detectado como un cuadrilátero y
para recuperar de forma inequívoca la orientación de sus esquinas [2].

### 2.2 Cálculo de escala

Si \(a_{mm}\) es el lado físico del marcador y \(a_{px}\) es su lado medio en
píxeles, la escala usada es

\[
k=\frac{a_{mm}}{a_{px}} \quad [\mathrm{mm/píxel}].
\]

Cada punto se convierte mediante

\[
\mathbf{q}_i=k\mathbf{p}_i.
\]

Esta lógica corresponde a las funciones `compute_scale` y `scale_points`, en
`src/fish_morphometry/measurements/direct_scale.py`. La función `measure_a`
selecciona la transformación `uniform_scale_approximation`, y `measure_direct`
aplica después las fórmulas morfométricas comunes.

El promedio de los cuatro lados reduce el efecto de pequeñas diferencias de
detección. El coeficiente de variación entre lados funciona como indicador de
deformación o de una observación poco confiable. Sin embargo, ese indicador no
demuestra por sí solo que la escala sea válida en el plano del pez.

### 2.3 Supuesto geométrico

Una sola escala es una transformación de similitud muy restringida. Supone que
el cambio de píxel a milímetro es uniforme en la región medida. Esto sería una
aproximación razonable si:

- el pez y el marcador estuvieran casi en el mismo plano;
- ese plano fuera aproximadamente paralelo al sensor;
- la perspectiva y la distorsión residual fueran pequeñas;
- la refracción no cambiara de manera relevante entre el marcador y el pez.

En el montaje de A, el marcador está en el vidrio y el pez se encuentra a otra
distancia. Por perspectiva, el tamaño proyectado depende de la profundidad. Por
refracción, el camino óptico tampoco se comporta exactamente como una cámara
pinhole en aire. Por tanto, A no puede trasladar de forma exacta la escala del
vidrio al plano del pez.

Esta es una limitación física inherente, no un error de programación. La
implementación actual la hace explícita mediante una advertencia y registra la
transformación como aproximación de escala uniforme.

### 2.4 Qué justifica y qué no justifica A

A sí permite construir una línea de base simple y repetible. Es útil para medir
cuánto mejora un método que considera la posición del pez o la refracción.

A no permite afirmar que:

- existe una escala global exacta en toda la imagen;
- el marcador del vidrio es coplanar con el pez;
- la perspectiva quedó corregida;
- la refracción aire–vidrio–agua quedó modelada.

Una diferencia entre A y B/C no debe atribuirse únicamente a la refracción,
porque también interviene la separación entre el plano del marcador y el plano
de medición.

---

## 3. Experimento A′: homografía de un marcador coplanar

### 3.1 Objetivo del método

A′ funciona como control directo de A. El marcador se ubica en el soporte de la
réplica y su cara impresa se alinea con el plano de simetría del pez. La
coplanaridad permite modelar la transformación completa entre el plano físico y
la imagen mediante una homografía [3, 4].

### 3.2 Homografía planar

Una homografía es una matriz (3\times3), definida salvo un factor de escala,
que relaciona puntos de dos planos en coordenadas homogéneas:

\[
\lambda
\begin{bmatrix}
X\\Y\\1
\end{bmatrix}
=
\mathbf{H}
\begin{bmatrix}
x\\y\\1
\end{bmatrix}.
\]

Después de realizar la división homogénea, \((X,Y)\) queda expresado en el plano
métrico. La homografía tiene ocho grados de libertad. Las cuatro esquinas del
marcador proporcionan cuatro correspondencias 2D–2D, suficientes para estimarla
cuando los puntos no forman una configuración degenerada [3, 4].

La función `marker_plane_homography` relaciona las cuatro esquinas observadas
con el cuadrado métrico

\[
(0,0),\ (a,0),\ (a,a),\ (0,a),
\]

donde \(a\) es el lado físico del ArUco. `transform_points_homography`
transforma \(p_1,\ldots,p_4\) con la matriz obtenida.

### 3.3 Transformación del eje anatómico

Una homografía no conserva de forma general las direcciones, los ángulos ni una
escala uniforme en toda la imagen. Por esa razón no es correcto transformar los
puntos y mantener sin cambios el eje definido en píxeles.

`transform_axis_homography` toma un punto de anclaje y un segundo punto de
prueba sobre el eje de imagen. Ambos se transforman mediante \(\mathbf{H}\). La
diferencia entre sus posiciones transformadas define la dirección del eje en el
plano métrico. Así, los puntos y el eje pertenecen al mismo espacio antes de
calcular \(L_T\) y \(P_C\).

### 3.4 Ventaja respecto de A

La homografía corrige el escorzo y la variación proyectiva dentro del plano del
marcador. Por eso A′ es teóricamente más adecuado que una escala uniforme cuando
el pez, el marcador y todos los puntos medidos son coplanares.

El campo `scale_mm_per_px` se conserva como una referencia nominal basada en el
lado medio del marcador, pero no es la transformación real de A′. La medición
usa la matriz completa y la escala local puede variar de un punto a otro.

### 3.5 Límites de A′

La homografía describe un plano, no un volumen. Si un punto anatómico está fuera
del plano del marcador, su transformación métrica contiene un error que depende
de la falta de coplanaridad y de la geometría de observación. Por este motivo,
`coplanarity_error_mm` se registra como una medición física externa y no se
intenta deducir de una sola imagen.

A′ tampoco corrige por sí solo:

- la distorsión de lente no eliminada previamente;
- una curvatura fuera del plano de la réplica;
- errores en el tamaño impreso o medido del marcador;
- la refracción de forma física explícita.

En la práctica, una homografía estimada en la imagen subacuática puede compensar
parte de la deformación observada **en ese mismo plano**, pero no convierte el
sistema completo en un modelo refractivo general.

---

## 4. Experimento B: cámara pinhole efectiva bajo agua

### 4.1 Idea general

B calibra el conjunto cámara–carcasa–agua como si fuera una cámara pinhole con
distorsión. Los parámetros obtenidos son efectivos: resumen empíricamente el
comportamiento observado durante la calibración, aunque la cámara física detrás
de un puerto plano no sea realmente de punto de vista único.

Este enfoque es frecuente como aproximación práctica. La literatura subacuática
indica que una calibración realizada bajo agua puede alcanzar buenos resultados
en una región limitada, pero la refracción de un puerto plano viola en general
el supuesto de que todos los rayos se originan en un único centro [8, 9].

### 4.2 Calibración efectiva de la cámara

El modelo pinhole ideal relaciona un punto 3D de cámara
\((X_c,Y_c,Z_c)\) con el píxel \((u,v)\):

\[
\lambda
\begin{bmatrix}u\\v\\1\end{bmatrix}
=
\mathbf{K}_B
\begin{bmatrix}X_c\\Y_c\\Z_c\end{bmatrix},
\]

donde

\[
\mathbf{K}_B=
\begin{bmatrix}
f_x&0&c_x\\
0&f_y&c_y\\
0&0&1
\end{bmatrix}.
\]

Los coeficientes \(\mathbf{D}_B\) representan la distorsión radial y tangencial
del modelo elegido. `calibrate_b_from_images` detecta un damero sumergido,
refina las esquinas a nivel subpíxel y estima \(\mathbf{K}_B,\mathbf{D}_B\),
rotaciones y traslaciones mediante `calibrateCamera`. La calibración con varias
vistas de un patrón plano se basa en el procedimiento de Zhang [5].

El error de reproyección compara las esquinas detectadas con las esquinas
proyectadas por el modelo. Un error pequeño indica consistencia entre las
observaciones y el modelo ajustado, pero no demuestra exactitud métrica fuera de
las posiciones observadas. Por eso el programa:

- exige varias vistas utilizables;
- rechaza vistas con error individual alto;
- comprueba diversidad espacial y angular del tablero;
- conserva el RMS y los errores por vista;
- requiere después una validación física independiente.

Los mínimos de vistas y los umbrales de píxeles son criterios operativos del
proyecto. No deben presentarse como valores universales.

### 4.3 Referencia entre cámara y rail

Para obtener un plano métrico se estima la pose de un tablero conocido mediante
`solvePnP`. Esta función busca la rotación y la traslación que reducen el error
de reproyección entre puntos 3D del tablero y sus observaciones 2D [6].

En `estimate_rail_reference_from_observations` se usan observaciones tomadas en
dos o más posiciones conocidas. Para cada posición se estima la pose del
tablero. Después se ajusta una recta a los puntos de traslación:

\[
\mathbf{P}(z)\approx\mathbf{P}_{ref}
+(z-z_{ref})\mathbf{r},
\]

donde \(\mathbf{r}\) es la dirección unitaria del rail. La dispersión de las
normales comprueba si los planos se mantienen paralelos, y el residuo del ajuste
indica si el desplazamiento observado es compatible con un movimiento lineal.

`build_measurement_plane` traslada el plano de referencia hasta la posición de
captura:

\[
\mathbf{P}_0=\mathbf{P}_{ref}
+(z_{captura}-z_{ref})\mathbf{r}
+o\mathbf{a},
\]

donde \(o\) es el desplazamiento firmado hasta el plano de simetría de la
réplica y \(\mathbf{a}\) puede ser la dirección del rail o la normal del plano,
según la configuración documentada.

### 4.4 De píxeles a rayos efectivos

`undistort_points_to_rays` aplica `cv2.undistortPoints` con
`P=None`. OpenCV devuelve coordenadas normalizadas cuando no se especifica una
nueva matriz de proyección [7]. Cada punto \((x_n,y_n)\) se interpreta como la
dirección efectiva

\[
\mathbf{r}=(x_n,y_n,1).
\]

La escala de esta dirección no importa, porque el rayo se escribe como

\[
\mathbf{X}(\lambda)=\lambda\mathbf{r},\qquad \lambda>0.
\]

### 4.5 Intersección rayo–plano

Sea un plano definido por un punto \(\mathbf{P}_0\) y una normal unitaria
\(\mathbf{s}\):

\[
\mathbf{s}\cdot(\mathbf{X}-\mathbf{P}_0)=0.
\]

Al sustituir el rayo se obtiene

\[
\lambda=\frac{\mathbf{s}\cdot\mathbf{P}_0}
{\mathbf{s}\cdot\mathbf{r}},
\qquad
\mathbf{X}=\lambda\mathbf{r}.
\]

Esta es la operación de `intersect_ray_plane`. Si el denominador es cercano a
cero, el rayo es paralelo o casi paralelo al plano y la solución se rechaza. Si
\(\lambda\leq0\), la intersección queda detrás de la cámara y tampoco es válida.

`intersect_image_points_with_plane` aplica el procedimiento a los cuatro puntos.
`image_axis_to_plane_direction` transforma dos puntos sobre el eje anatómico y
obtiene su dirección dentro del mismo plano métrico. Finalmente,
`measure_projected_morphometry_3d` calcula las medidas comunes.

### 4.6 Alcance y limitación de B

B incorpora la posición métrica del plano y la distorsión estimada bajo agua.
Por eso tiene más información geométrica que A y A′. Sin embargo, sus rayos
siguen partiendo de un único origen efectivo. En un puerto plano real, los
rayos refractados forman una cámara axial y no una cámara central pinhole [8].

La calibración efectiva puede absorber parcialmente la refracción cerca de la
zona y las condiciones de calibración. Su validez puede degradarse al cambiar:

- la distancia al vidrio;
- la región del encuadre;
- la orientación o el espesor del puerto;
- el medio o las condiciones del agua;
- el enfoque, el zoom o la resolución.

Por eso `validate_known_segment_b` mide un segmento sumergido de longitud
conocida y calcula

\[
e=L_{estimada}-L_{real},
\qquad
e_{\%}=100\frac{e}{L_{real}}.
\]

El resultado permanece `PENDING_VALIDATION` si no se definió un criterio de
aceptación. El RMS de calibración no reemplaza esta validación física.

---

## 5. Experimento C: modelo refractivo explícito

### 5.1 Idea general

C separa el modelo de la lente del modelo del puerto. Primero calibra la cámara
en aire para obtener sus parámetros intrínsecos y la distorsión. Después modela
dos refracciones: aire–vidrio y vidrio–agua.

Esta separación es coherente con la teoría de cámaras refractivas. En una
carcasa de puerto plano, la dirección del rayo cambia en cada interfaz según la
ley de Snell y el sistema deja de ser una cámara pinhole central ordinaria
[8–10].

### 5.2 Calibración en aire

`calibrate_air_from_images` estima \(\mathbf{K}_{air}\) y
\(\mathbf{D}_{air}\) mediante vistas de un damero. La lógica de detección,
refinamiento subpíxel, rechazo de vistas y diversidad geométrica es análoga a la
de B, pero los datos se adquieren en aire.

El píxel observado se corrige con `undistortPoints`. Las coordenadas
normalizadas forman el rayo de aire

\[
\mathbf{v}_{air}=
\frac{(x_n,y_n,1)}{\|(x_n,y_n,1)\|}.
\]

### 5.3 Geometría del puerto plano

`FlatPortParameters` describe:

- la normal unitaria del puerto \(\mathbf{m}\), orientada desde la cámara hacia
  la escena;
- la distancia \(d\) desde el centro de proyección hasta la primera interfaz;
- el espesor del vidrio \(t_g\);
- los índices \(n_{air}\), \(n_{glass}\) y \(n_{water}\).

Las dos interfaces paralelas se expresan como

\[
\mathbf{m}\cdot\mathbf{X}=d
\]

y

\[
\mathbf{m}\cdot\mathbf{X}=d+t_g.
\]

La distancia \(d\) debe referirse al centro de proyección de la cámara, no
simplemente al frente visible de la lente. Si se usa una aproximación física,
el programa exige registrarla como tal y acompañarla de una nota de
incertidumbre.

### 5.4 Ley de Snell en forma vectorial

Para una dirección incidente unitaria \(\mathbf{v}_i\), una normal unitaria
\(\mathbf{m}\) orientada hacia el medio de destino y los índices \(n_1,n_2\), se
define

\[
c_i=\mathbf{v}_i\cdot\mathbf{m},
\qquad
\eta=\frac{n_1}{n_2},
\]

\[
k=1-\eta^2(1-c_i^2).
\]

La dirección transmitida usada por `refract_direction` es

\[
\mathbf{v}_t=
\eta(\mathbf{v}_i-c_i\mathbf{m})+\sqrt{k}\,\mathbf{m}.
\]

El resultado se normaliza numéricamente. Si \(k<0\), no existe una dirección
transmitida real y se detecta reflexión interna total. También se rechaza una
dirección que no avance hacia la interfaz declarada.

Esta expresión es la versión vectorial de

\[
n_1\sin\theta_1=n_2\sin\theta_2.
\]

### 5.5 Trazado aire–vidrio–agua

`trace_refracted_ray` aplica la siguiente secuencia.

Primero, intersecta el rayo de aire con la interfaz aire–vidrio:

\[
\lambda_1=\frac{d}{\mathbf{m}\cdot\mathbf{v}_{air}},
\qquad
\mathbf{q}_1=\lambda_1\mathbf{v}_{air}.
\]

Luego calcula \(\mathbf{v}_{glass}\) mediante Snell entre aire y vidrio. El
avance dentro del vidrio es

\[
\lambda_g=\frac{t_g}{\mathbf{m}\cdot\mathbf{v}_{glass}},
\qquad
\mathbf{q}_2=\mathbf{q}_1+\lambda_g\mathbf{v}_{glass}.
\]

En \(\mathbf{q}_2\) se aplica nuevamente Snell para obtener
\(\mathbf{v}_{water}\). Finalmente, el rayo en agua es

\[
\mathbf{X}(\lambda)=\mathbf{q}_2+\lambda\mathbf{v}_{water}.
\]

Si el plano físico de medición está definido por \(\mathbf{P}_0,\mathbf{s}\),
su intersección se obtiene con

\[
\lambda=
\frac{\mathbf{s}\cdot(\mathbf{P}_0-\mathbf{q}_2)}
{\mathbf{s}\cdot\mathbf{v}_{water}}.
\]

Esta última expresión está implementada en `intersect_ray_line_plane`. Los
residuos de ambas interfaces comprueban numéricamente que \(\mathbf{q}_1\) y
\(\mathbf{q}_2\) satisfacen sus ecuaciones de plano.

### 5.6 Transformación del eje y medición

`_trace_to_plane` aplica el trazado completo a \(p_1,\ldots,p_4\).
`_refracted_axis_to_plane_direction` lo aplica también a un ancla y a un punto
de prueba sobre el eje anatómico. Con esto se evita mezclar un eje en píxeles
con puntos en el plano refractivo.

`measure_c` entrega los puntos métricos y conserva, para cada observación:

- \(\mathbf{v}_{air}\);
- \(\mathbf{q}_1\);
- \(\mathbf{v}_{glass}\);
- \(\mathbf{q}_2\);
- \(\mathbf{v}_{water}\);
- la intersección con el plano de medición.

Después usa exactamente las mismas definiciones de longitud y profundidad que
los otros experimentos. Por tanto, la comparación entre A, A′, B y C cambia el
modelo óptico, no la definición morfométrica.

### 5.7 Calibración refractiva con Calibmar

El proyecto puede importar un perfil `FLATPORT` de Calibmar. Este tipo de
calibración estima conjuntamente parámetros de cámara y parámetros del puerto.
Calibmar propone una implementación abierta para calibración refractiva de
carcasas planas o hemisféricas y ha sido evaluado con datos simulados y reales
[10].

En el importador actual, los parámetros de puerto se interpretan en el orden:

\[
[N_x,N_y,N_z,d,t_g,n_{air},n_{glass},n_{water}].
\]

Las unidades de \(d\) y \(t_g\) deben declararse y se convierten internamente a
milímetros. La resolución del perfil debe coincidir con la imagen usada para
medir.

### 5.8 Calidad, validación y sensibilidad

C rechaza configuraciones o rayos físicamente inconsistentes, por ejemplo:

- normales nulas o con sentido incorrecto;
- índices de refracción no positivos;
- intersecciones detrás del origen;
- rayos casi paralelos a una interfaz o al plano de medición;
- reflexión interna total;
- unidades o resoluciones incompatibles.

`validate_known_segment_c` aplica el mismo trazado a un segmento sumergido de
longitud conocida. La validación debe cubrir el centro y otras regiones del
encuadre, y repetirse en las posiciones experimentales relevantes. Un resultado
solo pasa a `PASS` cuando los registros compatibles cumplen los umbrales y la
cobertura espacial configurada.

El análisis de sensibilidad varía parámetros como \(d\), \(t_g\),
\(n_{water}\), la normal del puerto y el plano de medición. Su objetivo es
observar cuánto cambia la medida ante incertidumbres plausibles. No sustituye
una propagación formal de incertidumbre, pero ayuda a identificar los parámetros
que requieren una medición física más precisa.

### 5.9 Diferencia fundamental entre B y C

La pose cámara–rail calculada en B pertenece al sistema pinhole efectivo de B.
No debe reutilizarse directamente como plano físico de C. En C, los rayos parten
del centro de proyección de la cámara calibrada en aire y se desvían físicamente
en las interfaces. Por eso su plano debe estar medido o calibrado en el marco
`physical_camera_refractive`.

Esta separación está implementada de forma deliberada en
`measurement_plane_from_rail`, que rechaza la conversión automática de una
referencia B a un plano C.

---

## 6. Comparación teórica de los cuatro experimentos

| Aspecto | A | A′ | B | C |
|---|---|---|---|---|
| Referencia métrica | Lado de ArUco en vidrio | Cuadrado ArUco coplanar | Damero, pose y rail | Calibración en aire, puerto y plano físico |
| Transformación | Escala uniforme | Homografía planar | Rayo pinhole efectivo–plano | Trazado refractivo–plano |
| Considera perspectiva | Solo de forma aproximada | Sí, dentro del plano | Sí, mediante el modelo efectivo | Sí, mediante geometría física |
| Considera distorsión de lente | No explícitamente en la medición | No explícitamente en la medición | Sí, en \(\mathbf{D}_B\) | Sí, en \(\mathbf{D}_{air}\) |
| Considera refracción | No | Solo compensación empírica dentro del plano | Implícita en parámetros efectivos | Explícita con Snell |
| Requiere coplanaridad | No se cumple entre marcador y pez | Sí | Los puntos se suponen en el plano medido | Los puntos se suponen en el plano físico medido |
| Escala global mm/píxel | Sí, aproximada | No | No | No |
| Principal límite | Marcador y pez en planos distintos | Error fuera del plano | Modelo central aproximado | Sensibilidad a parámetros físicos |

La complejidad aumenta desde A hasta C, pero “más complejo” no significa
automáticamente “más exacto”. La exactitud debe comprobarse con referencias
físicas independientes. Una mala estimación del plano o de los parámetros del
puerto puede hacer que C sea peor que un método más simple bien controlado.

---

## 7. Correspondencia entre funciones y teoría

### A y A′

| Archivo o función | Justificación teórica |
|---|---|
| `methods/a.py::measure_a` | Define el marcador en el plano del vidrio y selecciona escala uniforme |
| `methods/a_prime.py::measure_a_prime` | Define el marcador coplanar y registra el error físico de coplanaridad |
| `methods/_direct.py::measure_direct` | Separa transformación métrica y cálculo morfométrico |
| `direct_scale.py::compute_scale` | Razón entre longitud física y longitud observada |
| `direct_scale.py::scale_points` | Transformación de similitud uniforme |
| `direct_scale.py::marker_plane_homography` | Correspondencia proyectiva entre dos planos |
| `direct_scale.py::transform_axis_homography` | Lleva el eje al mismo espacio que los puntos |

### B

| Archivo o función | Justificación teórica |
|---|---|
| `calibration/b_calibration.py::calibrate_b_from_images` | Ajuste pinhole efectivo con múltiples vistas y error de reproyección |
| `geometry/rail_plane.py::_solve_board_pose` | Estimación de pose 3D–2D mediante PnP |
| `estimate_rail_reference_from_observations` | Ajuste métrico de la dirección del rail y consistencia de planos |
| `build_measurement_plane` | Traslado del plano hasta la posición real de captura |
| `ray_plane.py::undistort_points_to_rays` | Conversión de píxeles distorsionados a rayos normalizados |
| `ray_plane.py::intersect_ray_plane` | Solución analítica de intersección rayo–plano |
| `methods/b.py::measure_b` | Integra el modelo B y aplica morfometría proyectada 3D |
| `validation/physical_b.py::validate_known_segment_b` | Contraste con una longitud física independiente |

### C

| Archivo o función | Justificación teórica |
|---|---|
| `calibration/air_calibration.py::calibrate_air_from_images` | Estima intrínsecos y distorsión de la cámara sin el efecto del agua |
| `geometry/snells_law.py::refract_direction` | Ley vectorial de Snell y detección de reflexión interna total |
| `geometry/refractive_port.py::trace_refracted_ray` | Propagación secuencial aire–vidrio–agua |
| `ray_plane.py::intersect_ray_line_plane` | Intersección del rayo acuático, con origen desplazado, y el plano físico |
| `methods/c.py::_trace_to_plane` | Reconstrucción métrica de los cuatro puntos |
| `methods/c.py::_refracted_axis_to_plane_direction` | Transformación refractiva del eje anatómico |
| `methods/c.py::measure_c` | Integra trazado, plano y morfometría proyectada |
| `validation/c_validation.py::validate_known_segment_c` | Validación métrica sumergida del modelo completo |

---

## 8. Supuestos que la tesis debe declarar de forma explícita

La teoría y el código no resuelven automáticamente las siguientes decisiones:

1. **Convención de longitud.** Debe precisarse si \(p_2\) representa longitud
   total, horquilla, longitud estándar u otra definición.
2. **Selección de profundidad.** Debe explicarse la región anatómica donde se
   busca \(p_3,p_4\) y cómo se excluyen las aletas.
3. **Origen del eje longitudinal.** Debe indicarse si procede de la orientación
   mecánica, una anotación manual, una máscara o un algoritmo automático.
4. **Tolerancia de sección.** El valor angular debe justificarse por el error
   admisible y, si es posible, evaluarse mediante sensibilidad.
5. **Coplanaridad.** A′, B y C miden correctamente solo los puntos que
   corresponden al plano asignado. Una réplica con espesor o inclinación fuera
   del plano introduce error.
6. **Estabilidad del montaje.** Enfoque, zoom, resolución, posición de cámara,
   orientación del puerto y estructura del rail deben permanecer controlados.
7. **Condiciones del agua.** En C, \(n_{water}\) está relacionado con las
   condiciones físicas del medio. Temperatura, salinidad y presión deben
   registrarse cuando sean relevantes.
8. **Criterios de aceptación.** Los umbrales de RMS, error por vista, error
   absoluto y error porcentual deben justificarse como decisiones del estudio,
   no como propiedades universales de los algoritmos.

---

## 9. Propuesta sencilla para redactar la metodología en la tesis

Una futura redacción en LaTeX podría organizarse así:

1. definir primero los puntos anatómicos y la convención caudal;
2. presentar las ecuaciones comunes de longitud y profundidad proyectadas;
3. describir A como línea de base con escala en el vidrio;
4. describir A′ como control coplanar con homografía;
5. explicar la calibración efectiva, el rail y la intersección rayo–plano de B;
6. explicar la calibración en aire, el puerto plano y Snell para C;
7. describir el protocolo de validación física común;
8. presentar por separado error, repetibilidad e incertidumbre;
9. comparar resultados sin confundir error anatómico, error de anotación y error
   óptico.

La hipótesis técnica que puede someterse a prueba es que una representación más
completa de la geometría óptica disminuye el error métrico, especialmente fuera
del plano del vidrio y hacia los bordes de la imagen. Esta hipótesis debe
evaluarse con datos físicos; no se considera demostrada por las ecuaciones ni
por el funcionamiento del código.

---

## 10. Resultado del análisis de la implementación

Las ecuaciones principales implementadas concuerdan con el modelo declarado
para cada experimento:

- la proyección anatómica de longitud y profundidad es coherente en 2D y 3D;
- A implementa correctamente una escala uniforme, siempre que se presente como
  aproximación y no como corrección física del medio;
- A′ aplica una homografía a los puntos y al eje, que es el procedimiento
  correcto bajo el supuesto de coplanaridad;
- B realiza correctamente la retroproyección pinhole efectiva y la intersección
  analítica con el plano de la réplica;
- C implementa de manera coherente dos interfaces paralelas, dos aplicaciones
  de la ley de Snell y una última intersección con el plano físico.

Este resultado indica concordancia matemática entre la teoría seleccionada y
las funciones principales. No demuestra todavía exactitud experimental. Esa
afirmación requiere comparar cada método con longitudes físicas conocidas.

También quedan límites que deben explicarse en la tesis:

- A y A′ no aplican en su flujo actual una corrección explícita de distorsión de
  lente antes de la escala o la homografía;
- las funciones de medición reciben (p_1,p_2,p_3,p_4) ya seleccionados: no
  demuestran que esos puntos sean anatómicamente correctos;
- en particular, el código valida la sección dada por (p_3,p_4), pero no busca
  por sí mismo la profundidad corporal máxima sobre todas las secciones;
- el eje longitudinal también se recibe como entrada y su exactitud depende del
  procedimiento utilizado para determinarlo;
- `coplanarity_error_mm` se registra, pero no se propaga todavía hasta una
  incertidumbre de A′;
- el análisis de sensibilidad de C no equivale a una propagación completa de
  incertidumbres correlacionadas;
- B y C dependen de que el plano de simetría represente realmente los puntos
  anatómicos observados.

Por estas razones, el software puede justificar el **modelo de cálculo**, pero
la tesis debe justificar por separado la selección anatómica, el montaje, los
umbrales y la incertidumbre final.

---

## 11. Referencias base

[1] Holden, M. J. y Raitt, D. F. S. (eds.). *Manual of Fisheries Science,
Part 2: Methods of Resource Investigation and their Application*. FAO, 1974.
Sección 3, medición de peces.
<https://www.fao.org/4/F0752E/F0752E03.htm>

[2] Garrido-Jurado, S., Muñoz-Salinas, R., Madrid-Cuevas, F. J. y
Marín-Jiménez, M. J. “Automatic generation and detection of highly reliable
fiducial markers under occlusion”. *Pattern Recognition*, 47(6), 2280–2292,
2014. <https://doi.org/10.1016/j.patcog.2014.01.005>

[3] Hartley, R. y Zisserman, A. *Multiple View Geometry in Computer Vision*,
2.ª ed., Cambridge University Press, 2004.
<https://doi.org/10.1017/CBO9780511811685>

[4] OpenCV. “Basic concepts of the homography explained with code”.
<https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html>

[5] Zhang, Z. “A Flexible New Technique for Camera Calibration”. *IEEE
Transactions on Pattern Analysis and Machine Intelligence*, 22(11), 1330–1334,
2000. <https://doi.org/10.1109/34.888718>

[6] OpenCV. “Perspective-n-Point (PnP) pose computation”.
<https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html>

[7] OpenCV. “Camera Calibration and 3D Reconstruction”, documentación de
`calibrateCamera`, `undistortPoints` y `projectPoints`.
<https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html>

[8] Agrawal, A., Ramalingam, S., Taguchi, Y. y Chari, V. “A Theory of
Multi-Layer Flat Refractive Geometry”. *IEEE Conference on Computer Vision and
Pattern Recognition*, 3346–3353, 2012.
<https://www.merl.com/publications/TR2012-047>

[9] Pedersen, M., Hein Bengtson, S., Gade, R., Madsen, N. y Moeslund, T. B.
“Camera Calibration for Underwater 3D Reconstruction Based on Ray Tracing Using
Snell's Law”. *CVPR Workshops*, 2018.
<https://openaccess.thecvf.com/content_cvpr_2018_workshops/w28/html/Pedersen_Camera_Calibration_for_CVPR_2018_paper.html>

[10] Seegräber, F., She, M., Woelk, F. y Köser, K. “A Calibration Tool for
Refractive Underwater Vision”. *ICCV Workshops*, 2087–2095, 2025.
<https://openaccess.thecvf.com/content/ICCV2025W/CVAUI%20%26%20AAMVEM/html/Seegraber_A_Calibration_Tool_for_Refractive_Underwater_Vision_ICCVW_2025_paper.html>

### Documentación complementaria de implementación

- OpenCV, “Camera Calibration”:
  <https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html>
- OpenCV, “Detection of ArUco Markers”:
  <https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html>
- Calibmar, documentación del proyecto:
  <https://mdskiel.github.io/calibmar_documentation/>
