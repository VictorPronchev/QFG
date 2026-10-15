# QFG Lab 5.2 за Blender

## 1.0.0-alpha B6 — blind Group-15 relaxation harness

B6 превръща Atlas/QFG стека в end-to-end blind протокол. Записва reproducible fingerprint на source/configuration, пуска B3 field coupling + B4 feedback + B5 admissibility projection и следи само предсказаната Group-15 валентна геометрия. Convergence detector-ът **не чете** experimental holdout registry. При convergence резултатът може автоматично да се freeze-не, а H-X-H референцията остава скрита до отделния Reveal бутон. Виж `B6_BLIND_PROTOCOL.md`.

## 0.9.0-alpha B5 — constraint-aware Atlas / molecular relaxation

B5 проектира предложенията за движение от B4 обратно в уловено допустимо геометрично множество: прегледана connectivity, radial shell distance, индивидуални angular freedom cones и symmetry groups. При C3 валентна група се пази уловеният azimuth pattern, но **общият polar tilt остава свободен**, така че молекулният pair angle може реално да се релаксира, вместо да е скрит като constraint. Projection law и stiffness параметрите остават изрично **CONDITIONAL**. Виж `B5_ATLAS_CONSTRAINTS.md`.

## 0.8.0-alpha B4 — двупосочна Atlas ↔ QFG обратна връзка

B4 затваря числения цикъл между прегледаната Atlas геометрия и живото редуцирано QFG поле. B3 продължава да превръща Atlas source-ите в scalar/vector поле, а B4 семплира еволюиралата QFG density/spin texture обратно върху Atlas source-ите и прилага **ограничена translation/rotation relaxation** с anchor restoring terms, твърди safety clamps и опционално повторно B3 rasterize-ване. Force/torque, mobility и work стойностите остават изрично **CONDITIONAL dimensionless proxies**, а не SI-калибрирана BSM-SG динамика. Виж `B4_ATLAS_FEEDBACK.md`.

### 0.7.0-alpha B3 — Atlas → QFG поле

B3 свързва маркираната BSM-SG/Atlas геометрия с живото редуцирано QFG поле. Геометрията може да е SOURCE/DERIVED, но kernel-ът, anisotropy law и абсолютната сила остават изрично CONDITIONAL. `REJECTED` източници никога не участват. Виж `B3_ATLAS_FIELD.md`.


## 0.6.0-alpha B2 — Atlas interaction laboratory

B2 надгражда Atlas Direct с консервативно auto-tagging по имена, interaction topology / `J_ij` proxy matrix, orbital-plane диагностика и ориентиран integrated-Bohr-envelope proxy. По подразбиране graph-ът е само topology и е DERIVED; overlap и inverse-cube kernel-ите са CONDITIONAL. Виж `B2_ATLAS_INTEGRATION.md`.

**Версия 1.0.0-alpha — модулна изследователска среда за Blender 5.2 LTS**

QFG Lab 5.2 събира в един Blender extension числените, визуалните и експерименталните прототипи, разработени около Q‑Field Geometry (QFG): 3D комплексно поле, редуциран спинорен/топологичен сектор, HRM и RF модели, топлинна обратна връзка, редуцирани gauge/gravity полета, Yb контролни модели и Molecular Creator bridge.

Добавката е **изследователски workbench**, а не твърдение за завършена или експериментално потвърдена фундаментална теория. Всеки модул ясно показва дали е числено ядро, редуциран модел, proxy или интерфейс към бъдещ външен решател.

## Изисквания

- Blender **5.2.0 LTS или по-нов от серията 5.2**.
- NumPy, включен в Blender — достатъчен за CPU режим.
- PyTorch е опционален за Torch CPU/CUDA backend. Добавката не го инсталира автоматично.

## Инсталиране

1. Не разархивирай файла `qfg_dynamics_blender_5_2_v1.0.0-alpha.zip`.
2. В Blender отвори **Edit → Preferences → Extensions**.
3. Избери менюто в горния десен ъгъл → **Install from Disk**.
4. Посочи ZIP файла и активирай **QFG Lab 5.2**.
5. В 3D Viewport натисни `N` и отвори таба **QFG 5.2**.

Архивът е Blender 5.2 extension: `blender_manifest.toml` и `__init__.py` са на най-горното ниво на ZIP файла.

## Най-сигурен първи тест

1. **Numerical Core → Backend: NumPy**.
2. **Grid: 32³**.
3. **Starting Scenes → Two-node collision**.
4. **Initialize QFG Engine**.
5. Натискай **Run QFG Steps** или използвай **Bake QFG Timeline**.
6. Прегледай `QFG_Field_Points`, изображението `QFG_Density_Slice` и диагностичния панел.

## Модули

### 1. 3D QFG поле

- комплексно scalar поле или редуциран двукомпонентен spinor;
- периодична 3D FFT решетка и Strang split-step еволюция;
- Gaussian възли, Hopf-ring ansatz, vortex и plane-wave актьори;
- phase kicks/импулси, статични потенциални и затихващи граници;
- `Z(ρ) = 1 + α(ρ − ρ₀)`, λ кохезия, κ стабилизация и Δ анизотропия;
- NumPy CPU и опционален Torch CPU/CUDA backend.

### 2. Топологичен сектор

- ориентационно поле `n = Ψ†σΨ / ρ`;
- reduced Skyrme/Faddeev energy density;
- Skyrme backreaction върху ефективния потенциал;
- Hopf/helicity и texture-gradient proxy метрики;
- winding параметри за ring/vortex начални конфигурации.

Proxy стойностите са сравнителни числени метрики. Те не са автоматично доказани цели топологични инварианти без convergence и boundary анализ.

### 3. Термодинамика

- спектрална температурна дифузия;
- локално collision heating;
- температурно зависима λ кохезия;
- ограничаване на температурата и диагностика на максимума.

### 4. HRM, RF и резонатори

- dual-frequency HRM pump с uniform, Gaussian, standing-wave или radial профил;
- HRM `(f₁,f₂)` scan и heatmap на `modeVar`;
- FFT, sidebands, sum/difference и IMD кандидати `2f₁−f₂`, `2f₂−f₁`;
- phase-noise и Allan-deviation proxies;
- нелинеен RF/Duffing/Kerr reduced-order model с forward/reverse sweep;
- cavity QFG-vs-thermal shift sweep;
- glow-plasma envelope и dielectric-boundary proxy;
- MEMS geometry/Q proxy.

### 5. Редуциран U(1)-подобен gauge сектор

- динамични векторни полета `A` и `E`;
- curl/curl спектрална еволюция и затихване;
- ток, оценен от комплексната фаза на Q-полето;
- gauge energy и опционална backreaction.

Това не е пълен ковариантен Maxwell–QFG решател и не претендира за SU(2) gauge динамика.

### 6. Weak-field gravity proxy

- Poisson solve от локалната енергийна/плътностна структура;
- гравитационен потенциал и energy proxy;
- опционална слаба backreaction.

Това не е динамичен метричен или Einstein-equation solver.

### 7. Yb research module

- Rabi и Ramsey traces;
- ODMR-like detuning sweep;
- cavity-Q sweep;
- two-ion phase accumulation proxy;
- отделно conventional baseline и кандидат QFG correction чрез `Z(ρ)` и texture terms.

Модулът е за планиране и сравнение на хипотези. Той не е пълен модел на Yb:YAG, trapped-ion система, crystal-field Hamiltonian или open-system master equation.

### 8. Molecular Creator bridge

- атоми като Blender обекти, автоматично разпознаване на връзки и визуализация;
- прозрачни Coulomb, overlap/coherence, β-gradient, γ-kinetic и η-topology proxy членове;
- предиктори за band gap, λmax, oscillator strength, coherence, stability и synthetic complexity;
- target objective и derivative-free geometry optimizer;
- начални системи H₂, H₂O и C₆H₆.

Това **не е** самосъгласуван Kohn–Sham/QFG‑DFT решател. Архитектурата е подготвена за бъдещо свързване към валидиран electronic-structure backend.

### 9. Atlas Direct / B2 / B3 / B4

- SOURCE/DERIVED извличане на nucleon/valence геометрия от реалните Blender transforms;
- interaction graph, orbital-plane и integrated-envelope diagnostics;
- CONDITIONAL Atlas scalar/vector field към живия QFG engine;
- **B4:** ограничена QFG→Atlas translation/rotation обратна връзка с anchors, safety clamps и опционално B3 re-rasterize-ване;
- force/torque/work-proxy telemetry с изрична CONDITIONAL provenance;
- `REJECTED` assumptions не участват нито в field generation, нито във feedback.

Виж `ATLAS_DIRECT.md`, `B2_ATLAS_INTEGRATION.md`, `B3_ATLAS_FIELD.md` и `B4_ATLAS_FEEDBACK.md`.

### 10. Blender визуализация и експортиране

- mesh vertices + Geometry Nodes `Mesh to Points`, без остарелия `PointCloud.points.add()` API;
- central density slice и heatmap planes;
- curve plots за RF, Yb, molecular objective и други резултати;
- timeline bake — тежката FFT симулация се изпълнява при bake, не във всеки playback handler;
- CSV, JSON и compressed NPZ export.

## Готови сцени

- Two-node collision
- Hopf-ring prototype
- HRM cavity prototype
- Thermal collision
- Gauge + gravity laboratory
- Plasma boundary laboratory
- Vortex laboratory

## Научно правилна интерпретация

Добавката различава:

1. визуален резултат от избрани уравнения и начални условия;
2. числено устойчив резултат при промяна на `dt`, grid, domain и backend;
3. предварително формулирана количествена прогноза;
4. сигнал, оцелял след control runs и uncertainty analysis;
5. експериментално различаване между QFG и конвенционален модел.

Само последните две нива могат да имат физическа валидираща стойност. Красива Blender анимация сама по себе си не доказва частица, нова сила, квантов процесор или енергиен механизъм.

## Какво още не е „пълно QFG“

Версия 1.0.0-alpha не съдържа:

- пълната ковариантна Euler–Lagrange система на предложения лагранжиан;
- самосъгласувана динамика на U(1) и SU(2) gauge полета;
- динамична метрика и Einstein solver;
- SI калибрация на всички параметри;
- converged minimum-energy Hopfion solver;
- извличане на квантувани заряд, маса и спин;
- реален QFG‑DFT/Kohn–Sham SCF;
- Bayesian molecular graph generator;
- директно управление на NI‑DAQ, FPGA, лазер, RF генератор или фотодиод;
- convex-hull/triangle-mesh collision, joints, CCD, broad-phase acceleration, sleeping islands, deformables и engineering-grade contact calibration.

Тези части са оставени като ясни модулни граници, вместо да бъдат представяни като готови чрез декоративен код.

## Лиценз

Blender extension пакетът е под **GNU GPL v3.0 or later**, за да е съвместим с изискванията за Blender add-ons. Виж `LICENSE`.



## Ново във v0.4.1 Alpha: безопасен playback и 6-DoF debug overlay

- Ясни режими извън baked диапазона: **Hold nearest baked frame**, **Clamp timeline** и **Status only**.
- Status редът показва отделно поисканата Blender рамка и реално визуализираната cached рамка.
- Timeline cache вече пази world telemetry, включително linear/angular momentum и активни контакти.
- Viewport debug за контактни точки, нормали и impulse вектори.
- Опционални вектори за total force, total torque и angular velocity.
- Малък 6-DoF HUD за body/floor contacts, kinetic-energy split, momentum, angular momentum, force и torque.
- Debug визуализацията е само display слой; frame handler-ът никога не стартира solver стъпки.

## Ново във v0.4.0 Alpha: 6-DoF QFG Dynamics

- quaternion ориентация и ъглова скорост;
- Sphere и ориентиран Box (OBB) collision shape;
- shape-dependent inertia tensor;
- Sphere/Sphere, Sphere/Box и Box/Box SAT контакти;
- импулс в реалната контактна точка и въртящ момент `r × J`;
- триене, което може физически да завърта телата;
- external torque и opt-in field-alignment torque;
- force/torque telemetry, rotational kinetic energy и angular momentum;
- baked playback на позиция и quaternion orientation.

Това остава изследователски reduced rigid-body runtime, а не заместител на валидиран engineering physics solver.
