"""
Vademécum Oficial Gutis Nicaragua 2026 y Mapeo Terapéutico.
Basado estrictamente en las especificaciones del Vademecum oficial.
"""

MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {
        "producto": "Talerdín",
        "clase_terapeutica": "Antihistamínicos Sistémicos (R06A)",
        "prioridad": 1,
        "apto_pediatria": True,
        # CORREGIDO: Se elimina " MONTELUKAST" que provocaba falso positivo con Ventilar
        "terminos_busqueda": [
            "TALERDIN", "CETIRIZINA", "CETRILER", "ALERCET", "DEGRALER",
            "LEVOCETIRIZINA", "DESLORATADINA", "LORATADINA", "FEXOFENADINA",
            "ALERFIN", "ZYRTEC", "AERIUS", "AVIANT", "BILAXTEN", "MEGATADINA",
            "RUPAX", "ALLEGRA", "RUPATADINA"
        ],
        "paciente_meta": "Pacientes con rinitis alérgica, conjuntivitis alérgica, urticaria crónica o prurito que requieren control antihistamínico seguro",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con rinitis alérgica, urticaria o prurito que requieren alivio seguro sin irritación gástrica",
        "caracteristica": "Cetirizina en Tabletas (10 mg), Jarabe (60 ml 100% libre de alcohol) y Solución Gotas (10 ml: 1 gota por cada 2 kg de peso en menores de 2 años)",
        "beneficio": "garantiza apego total al tratamiento sin rechazo por sabor ni efectos adversos gástricos asociados a excipientes alcohólicos",
        "arg_imagen": "proyecta ante la familia una prescripción de alta pureza galénica que evita molestias gástricas y asegura noches tranquilas",
        "arg_finanzas": "optimiza la economía familiar gracias a su concentración exacta (1 gota por cada 2 kg en lactantes) que evita desperdicios",
        "nicho_flanqueo": "lactantes y pacientes con mucosa gástrica sensible o intolerancia al excipiente alcohólico de otros antihistamínicos",
        "love_brand": "Tranquilidad nocturna para el paciente y su familia desde la primera toma, libre de alcohol."
    },
    "MR BIOTOS": {
        "producto": "Biotos Inmune",
        "clase_terapeutica": "Expectorantes, Antitusivos y Fitofármacos Respiratorios (R05C)",
        "prioridad": 1,
        "apto_pediatria": True,
        "terminos_busqueda": [
            "BIOTOS", "EXPECTORANTE", "FITOFARMACO", "ANTITUSIVO", "HEDERA",
            "PELARGONIUM", "ABRILAR", "TUSILEXIL", "PROSPAN", "UMCKALOABO",
            "KALOBIN", "MENAXOL", "BRONCODIL", "BROSOL", "HISTALIN"
        ],
        "paciente_meta": "Pacientes con tos seca, tos con flemas y secreción nasal en resfriado común, bronquitis, rinosinusitis y faringitis viral",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 años) con IVRS virales, tos seca o productiva y dificultad para expulsar secreciones",
        "caracteristica": "Fórmula fitofarmacológica dual única: Hedera hélix (35 mg) + Pelargonium sidoides (12.5 mg) en presentación Pediátrica (120 ml) y Adulto (170 ml)",
        "beneficio": "alivia la tos seca y con flemas mientras estimula los mecanismos defensivos antivirales y antibacterianos mediante su efecto inmunorregulador",
        "arg_imagen": "posiciona su receta un paso adelante del mucolítico tradicional, resolviendo tanto la tos como la respuesta inmune local",
        "arg_finanzas": "integra en un solo frasco (120 ml pediátrico o 170 ml adulto) la acción expectorante, antitusiva e inmunomoduladora",
        "nicho_flanqueo": "pacientes con cuadros respiratorios virales donde un expectorante simple no aporta acción inmunorreguladora",
        "love_brand": "Devolver la respiración libre y estimular las defensas naturales con respaldo científico."
    },
    "MR CLEMBROXIL": {
        "producto": "Clembroxil Compuesto",
        "clase_terapeutica": "Mucolíticos y Broncodilatadores Asociados (R05C / R03C)",
        "prioridad": 1,
        "apto_pediatria": True,
        "terminos_busqueda": [
            "CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOLITICO", "MUCOSOLVAN",
            "BROXOL", "SEKRETO", "BRONCODILATADOR", "FILINAR"
        ],
        "paciente_meta": "Pacientes con patologías respiratorias agudas y crónicas que cursan con retención de secreciones y broncoespasmo",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con broncoespasmo, sibilancias y retención severa de flemas (dosificación a 2 gotas por kg de peso)",
        "caracteristica": "Sinergia de Ambroxol (7.5 mg) + Clenbuterol (5 mcg) en Jarabe (120 ml) y Solución Gotas Pediátricas (20 ml), 100% libre de azúcar y alcohol",
        "beneficio": "dilata el bronquio y fluidifica el moco simultáneamente, despejando la vía aérea sin irritación por azúcar o alcohol",
        "arg_imagen": "respalda su diagnóstico en cuadros obstructivos complejos con un alivio respiratorio rápido desde las primeras tomas",
        "arg_finanzas": "ofrece frasco gotero de 20 ml o jarabe de 120 ml libre de azúcar y alcohol que cubre el esquema completo",
        "nicho_flanqueo": "pacientes con tos espástica y cierre bronquial donde un mucolítico simple no resuelve el broncoespasmo",
        "love_brand": "Respaldo respiratorio contundente y seguro cuando al paciente le falta el aire."
    },
    "MR MOMETZONA": {
        "producto": "Mometzona",
        "clase_terapeutica": "Corticosteroides y Descongestivos Nasales Tópicos (R01A)",
        "prioridad": 1,
        "apto_pediatria": True,
        "terminos_busqueda": [
            "MOMETZONA", "MOMETASONA", "NASAL", "NASONEX", "GAMMAFLUX", "AVAMYS",
            "FLUTICASONA", "BUDESONIDA", "RINOCLENIL", "OXALIP", "RYALTRIS",
            "FLUTIMIST", "NASOCROM", "BUDENA", "MOMMEX", "SIRYALE", "SUAVICORT",
            "HESTARIN", "NIMBON", "FLULERG", "DIMUXON", "MOMETA", "RINARIS"
        ],
        "paciente_meta": "Pacientes con rinitis alérgica u obstrucción nasal inflamatoria que requieren control local sin irritación",
        "paciente_meta_ped": "Pacientes pediátricos (2 a 11 años: 1 pulsación al día) y adolescentes con rinitis alérgica y congestión nasal persistente",
        "caracteristica": "Mometasona furoato al 0.05% en spray nasal acuoso (140 aplicaciones), suspensión 100% libre de alcohol",
        "beneficio": "desinflama la mucosa nasal desde la primera aplicación diaria sin causar ardor, resequedad ni epistaxis",
        "arg_imagen": "asegura que el paciente cumpla el tratamiento nasal sin ardor gracias a su vehículo acuoso libre de alcohol",
        "arg_finanzas": "entrega 140 dosis exactas de alta estabilidad que garantizan más de un mes completo de control continuo",
        "nicho_flanqueo": "pacientes con mucosa nasal hipersensible que abandonan otros sprays de la categoría por ardor",
        "love_brand": "Descongestionar y devolver el descanso reparador con suavidad acuosa libre de alcohol."
    },
    "MR VENTILAR": {
        "producto": "Ventilar",
        "clase_terapeutica": "Antileucotrienos y Antiasmáticos Sistémicos (R03D)",
        "prioridad": 1,
        "apto_pediatria": True,
        "terminos_busqueda": [
            "VENTILAR", "MONTELUKAST", "ANTILEUCOTRIENO", "LEUCOTRIENO", "SINGULAIR",
            "AIRUM", "SUVIAR", "LUKAST", "TELUKAST", "MONTEK"
        ],
        "paciente_meta": "Pacientes con asma bronquial o rinitis alérgica que requieren control preventivo nocturno",
        "paciente_meta_ped": "Pacientes pediátricos desde los 6 meses hasta los 14 años con hiperreactividad bronquial, asma o rinitis alérgica",
        "caracteristica": "Montelukast sódico en 3 presentaciones: 4 mg masticable sabor naranja (6 meses a 5 años), 5 mg masticable sabor tutti-chicle (6 a 14 años) y 10 mg recubierto",
        "beneficio": "logra excelente adherencia pediátrica por su sabor agradable y control sostenido de leucotrienos con una sola toma nocturna",
        "arg_imagen": "consolida el control preventivo a largo plazo evitando crisis nocturnas y visitas de urgencia",
        "arg_finanzas": "permite sostener terapias preventivas prolongadas mes a mes con accesibilidad económica real",
        "nicho_flanqueo": "pacientes en control preventivo continuo que abandonan otros esquemas por costo o rechazo al sabor",
        "love_brand": "Libertad para que el paciente descanse toda la noche sin crisis respiratorias."
    },
    "MR GASTROALIVIO": {
        "producto": "Gastroalivio",
        "clase_terapeutica": "Inhibidores de la Bomba de Protones y Antiulcerosos (A02B)",
        "prioridad": 1,
        "apto_pediatria": False,
        "terminos_busqueda": [
            "GASTROALIVIO", "ESOMEPRAZOL", "OMEPRAZOL", "PANTOPRAZOL", "LANSOPRAZOL",
            "DEXLANSOPRAZOL", "ANTIULCEROSO", "IBP", "NEXIUM", "CARBUM", "DEXIVANT",
            "ULCOZOL", "ESOZ"
        ],
        "paciente_meta": "Pacientes adultos con ERGE, gastropatía por AINEs, hiperclorhidria o en erradicación de Helicobacter pylori",
        "paciente_meta_ped": "Pacientes adolescentes mayores y adultos con ERGE o gastritis erosiva",
        "caracteristica": "Esomeprazol 40 mg en cápsulas de liberación retardada con micropellets gastrorresistentes (libre de gluten y lactosa) + Plan Paciente 2+1",
        "beneficio": "brinda protección gástrica y control ácido por 24 horas completas, respaldado por el Plan Paciente 2+1 (compra 2 cajas y recibe 1 gratis)",
        "arg_imagen": "asegura la remisión sintomática desde los primeros días evitando el reflujo nocturno gracias a la tecnología de micropellets",
        "arg_finanzas": "otorga un ahorro directo del 33% mediante el Plan Paciente 2+1 en farmacia, asegurando las semanas completas de terapia",
        "nicho_flanqueo": "pacientes con ERGE nocturno donde otros IBPs no sostienen las 24 horas o el paciente abandona por costo",
        "love_brand": "Tecnología de micropellets y respaldo 2+1 que protegen el estómago y la economía del paciente."
    },
    "MR DALIVIO": {
        "producto": "Dalivio / Dalivio Tramax",
        "clase_terapeutica": "Analgésicos y Antiinflamatorios No Esteroideos - AINEs (M01A / N02B)",
        "prioridad": 1,
        "apto_pediatria": False,
        "terminos_busqueda": [
            "DALIVIO", "DEXKETOPROFENO", "TRAMAX", "ANALGESICO", "AINE",
            "ENANTYUM", "STADIUM", "KETOROLACO", "DOLGENAL", "DICLOFENACO",
            "DICLO K", "FLAMYDOL", "ETORICOXIB", "CELECOXIB"
        ],
        "paciente_meta": "Pacientes adultos con dolor agudo de moderado a intenso (musculoesquelético, dismenorrea, odontalgia, cólico renal o postoperatorio)",
        "paciente_meta_ped": "Pacientes adolescentes mayores con dolor agudo traumático, odontalgia o dismenorrea",
        "caracteristica": "Dexketoprofeno en 3 vías (Tabletas 25 mg, Solución oral bebible 25 mg/10 ml e Inyectable 50 mg/2 ml) + Dalivio Tramax (Dexketoprofeno 25 mg + Tramadol 75 mg)",
        "beneficio": "proporciona alivio rápido y potente del dolor agudo en minutos (sobre bebible o ampolla) y analgesia multimodal en dolor severo",
        "arg_imagen": "devuelve la movilidad y el alivio al paciente en los primeros 15 a 30 minutos con menor carga racémica sobre la mucosa gástrica",
        "arg_finanzas": "permite rescate rápido en sobre bebible o ampolla y continuidad en tabletas sin requerir gastroprotección adicional costosa",
        "nicho_flanqueo": "pacientes con dolor agudo severo donde otros AINEs tardan más en actuar o irritan la mucosa gástrica",
        "love_brand": "Aliados del alivio rápido para devolverle la funcionalidad al paciente en minutos."
    },
    "MR CONFLEXIL": {
        "producto": "Conflexil / Conflexil Plus Shot",
        "clase_terapeutica": "Miorrelajantes de Acción Central y Combinaciones (M03B)",
        "prioridad": 2,
        "apto_pediatria": False,
        "terminos_busqueda": [
            "CONFLEXIL", "TIOCOLCHICOSIDO", "MIORRELAJANTE", "RELAJANTE MUSCULAR",
            "TIZANIDINA", "CICLOBENZAPRINA", "SIRDALUD", "DORIXINA RELAX"
        ],
        "paciente_meta": "Pacientes adultos y adolescentes (>16 años) con contracturas musculares, cervicalgia, dorsalgia o lumbalgia aguda",
        "paciente_meta_ped": "Adolescentes a partir de los 16 años con contracturas musculares deportivas o posturales",
        "caracteristica": "Conflexil (Tiocolchicósido 4 mg y Fuerte 8 mg que NO produce sueño) + Conflexil Plus Tabletas y Shot (bebible en stick pack con Tiocolchicósido 4 mg + Diclofenaco potásico 50 mg)",
        "beneficio": "ejerce triple acción (analgésica, antiinflamatoria y miorrelajante) de rápida absorción en Shot bebible, sin sedación diurna",
        "arg_imagen": "resuelve la contractura muscular permitiendo que el paciente siga trabajando sin la somnolencia de otros relajantes",
        "arg_finanzas": "reúne en un solo stick bebible o tableta el miorrelajante y el antiinflamatorio potásico de acción rápida",
        "nicho_flanqueo": "pacientes laboralmente activos con lumbalgia o contractura que no pueden permitirse somnolencia",
        "love_brand": "Liberar el movimiento del paciente sin adormecer su ritmo de vida."
    },
    "MR VALERPAN": {
        "producto": "Valerpan",
        "clase_terapeutica": "Corticosteroides Sistémicos Inyectables (H02A)",
        "prioridad": 2,
        "apto_pediatria": True,
        "terminos_busqueda": [
            "VALERPAN", "BETAMETASONA", "CORTICOSTEROIDE", "CELESTONE",
            "DIPROSPAN", "CRONODOSIS", "DEXAMETASONA", "ALIN", "UPRAL"
        ],
        "paciente_meta": "Pacientes con procesos inflamatorios severos, crisis alérgicas agudas o patologías articulares que requieren corticoterapia de doble acción",
        "paciente_meta_ped": "Pacientes con cuadros alérgicos o inflamatorios agudos severos que requieren control inmediato y sostenido",
        "caracteristica": "Fosfato sódico de Betametasona + Dipropionato de Betametasona en ampolla de 1 ml y 2 ml con óptima homogeneidad",
        "beneficio": "asegura doble acción comprobada: inicio rápido a los 30 minutos (fosfato) y efecto prolongado hasta por 30 días (dipropionato)",
        "arg_imagen": "evita el dolor en el sitio de inyección gracias a su micronización homogénea y previene el efecto rebote",
        "arg_finanzas": "resuelve el cuadro agudo y sostiene el control inflamatorio en una sola aplicación",
        "nicho_flanqueo": "cuadros inflamatorios o alérgicos agudos donde un corticoide simple pierde efecto rápido",
        "love_brand": "Calidad garantizada con acción inmediata en 30 minutos y respaldo prolongado."
    },
    "MR RENOVART": {
        "producto": "Renovart Platinum",
        "clase_terapeutica": "Condroprotectores y Salud Articular (M01C / M09A)",
        "prioridad": 2,
        "apto_pediatria": False,
        "terminos_busqueda": [
            "RENOVART", "COLAGENO", "GLUCOSAMINA", "CONDROITINA", "CONDROPROTECTOR",
            "ARTICULAR", "CURCUMA", "ARTROSIS"
        ],
        "paciente_meta": "Pacientes adultos con dolor articular inflamatorio, desgaste de cartílago o enfermedades degenerativas articulares",
        "paciente_meta_ped": "Adolescentes deportistas con sobrecarga articular",
        "caracteristica": "Fórmula pentavalente en sticks sabor naranja: Colágeno 100% hidrolizado bioactivo (10 g) + Cúrcuma longa (400 mg) + N-AcetilGlucosamina (1000 mg) + Condroitina (800 mg) + Vitamina C (60 mg)",
        "beneficio": "nutre el cartílago y controla el dolor e inflamación articular gracias a los curcuminoides, sin azúcar ni lactosa",
        "arg_imagen": "ofrece el condroprotector más completo del mercado que disminuye la rigidez y el dolor desde el primer mes",
        "arg_finanzas": "integra 5 componentes terapéuticos en un solo sobre diario, evitando compras separadas",
        "nicho_flanqueo": "pacientes con artrosis donde un colágeno simple sin cúrcuma ni glucosamina no alivia el dolor articular",
        "love_brand": "Fortalecer las articulaciones y favorecer la movilidad diaria con la fórmula más completa."
    },
    "MR MUPIRAL": {
        "producto": "Mupiral",
        "clase_terapeutica": "Antibióticos Tópicos Dermatológicos (D06A)",
        "prioridad": 2,
        "apto_pediatria": True,
        "terminos_busqueda": ["MUPIRAL", "MUPIROCINA", "ANTIBIOTICO TOPICO", "BACTROBAN", "ACIDO FUSIDICO"],
        "paciente_meta": "Pacientes con infecciones bacterianas primarias o secundarias de la piel (impétigo, foliculitis, heridas, quemaduras)",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 meses de edad) con impétigo, foliculitis o heridas sobreinfectadas",
        "caracteristica": "Mupirocina al 2% en ungüento tópico (tubo de 15 g), seguro en adultos y niños desde los 2 meses de edad",
        "beneficio": "logra erradicación bacteriana localizada altamente eficaz con excelente tolerabilidad cutánea",
        "arg_imagen": "asegura resolución rápida de infecciones cutáneas sin riesgo de resistencia cruzada sistémica",
        "arg_finanzas": "su tubo de 15 g rinde el tratamiento tópico completo sin requerir segundo envase",
        "nicho_flanqueo": "infecciones cutáneas o heridas donde otros antibióticos tópicos presentan resistencia",
        "love_brand": "Seguridad antibiótica tópica de primera línea desde los 2 meses de edad."
    },
    "MR BICORPAN": {
        "producto": "Bicorpan",
        "clase_terapeutica": "Corticosteroides Tópicos Combinados Polivalentes (D07C)",
        "prioridad": 2,
        "apto_pediatria": True,
        "terminos_busqueda": ["BICORPAN", "DERMATITIS", "TOLNAFTATO", "QUADRIDERM", "TRIDERM"],
        "paciente_meta": "Pacientes (>12 años y adultos) con dermatitis inflamatorias complicadas con infecciones por bacterias y/o hongos",
        "paciente_meta_ped": "Pacientes mayores de 12 años con dermatitis alérgica o por contacto sobreinfectada",
        "caracteristica": "Fórmula cuádruple en crema (15 g): Betametasona + Gentamicina + Tolnaftato + Yodoclorohidroxiquinoleína",
        "beneficio": "controla simultáneamente inflamación, prurito, infección bacteriana y micosis en lesiones dérmicas mixtas",
        "arg_imagen": "frena el prurito y la inflamación desde las primeras aplicaciones cubriendo bacterias y hongos",
        "arg_finanzas": "resuelve lesiones dérmicas mixtas en un solo tubo de 15 g",
        "nicho_flanqueo": "dermatitis mixtas rebeldes donde una crema simple no cubre hongos y bacterias a la vez",
        "love_brand": "Resolución integral para afecciones complejas de la piel."
    },
    "MR FEMGYL": {
        "producto": "Femgyl",
        "clase_terapeutica": "Anticonceptivos Hormonales Inyectables (G03A)",
        "prioridad": 3,
        "apto_pediatria": False,
        "terminos_busqueda": ["FEMGYL", "NORETISTERONA", "MESIGYNA", "ANTICONCEPTIVO INYECTABLE"],
        "paciente_meta": "Pacientes en edad reproductiva que buscan anticoncepción hormonal mensual cómoda y segura",
        "paciente_meta_ped": "Pacientes ginecológicas en control anticonceptivo",
        "caracteristica": "Enantato de noretisterona (50 mg) + Valerato de estradiol (5 mg) en ampolla de 1 ml mensual",
        "beneficio": "ofrece alta eficacia anticonceptiva en una sola aplicación mensual que evita olvidos diarios",
        "arg_imagen": "brinda seguridad anticonceptiva con excelente control del ciclo menstrual",
        "arg_finanzas": "esquema mensual accesible con calidad hormonal certificada",
        "nicho_flanqueo": "usuarias que olvidan la toma diaria de tabletas orales",
        "love_brand": "Tranquilidad y confianza mensual en salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen",
        "clase_terapeutica": "Anticonceptivos Hormonales Orales (G03A)",
        "prioridad": 3,
        "apto_pediatria": False,
        "terminos_busqueda": ["NORGYLEN", "LEVONORGESTREL", "ETINILESTRADIOL", "MICROGYNON", "ANTICONCEPTIVO ORAL"],
        "paciente_meta": "Pacientes que requieren anticoncepción oral hormonal combinada confiable",
        "paciente_meta_ped": "Pacientes ginecológicas en regulación de ciclo",
        "caracteristica": "Levonorgestrel (0.15 mg) + Etinilestradiol (0.03 mg) en caja con 21 tabletas recubiertas",
        "beneficio": "garantiza control predecible del ciclo menstrual con alta eficacia y seguridad",
        "arg_imagen": "estabilidad hormonal confiable respaldada por Gutis",
        "arg_finanzas": "alta accesibilidad mensual para la continuidad anticonceptiva",
        "nicho_flanqueo": "pacientes que buscan estabilidad hormonal oral con respaldo farmacéutico",
        "love_brand": "Cuidado confiable todos los días para la mujer."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit",
        "clase_terapeutica": "Ansiolíticos Benzodiazepínicos (N05B)",
        "prioridad": 3,
        "apto_pediatria": False,
        "terminos_busqueda": ["ANSIOLIT", "ALPRAZOLAM", "ANSIOLITICO", "TAFIL"],
        "paciente_meta": "Pacientes adultos con ansiedad generalizada, ansiedad asociada a depresión o estados de pánico",
        "paciente_meta_ped": "Pacientes adultos en manejo de ansiedad",
        "caracteristica": "Alprazolam 0.5 mg en tabletas ranuradas para dosificación individualizada",
        "beneficio": "logra rápido control de las crisis de ansiedad y síntomas somáticos asociados",
        "arg_imagen": "permite titular la dosis con precisión gracias a su tableta ranurada",
        "arg_finanzas": "tratamiento ansiolítico accesible y seguro",
        "nicho_flanqueo": "pacientes con crisis de angustia o insomnio por ansiedad aguda",
        "love_brand": "Paz mental y control oportuno en trastornos de ansiedad."
    },
    "MR DEPAX": {
        "producto": "Depax",
        "clase_terapeutica": "Antidepresivos ISRS - Sertralina (N06A)",
        "prioridad": 3,
        "apto_pediatria": False,
        "terminos_busqueda": ["DEPAX", "SERTRALINA", "ALTRULINE", "ZOLOFT"],
        "paciente_meta": "Pacientes adultos con depresión, TOC, trastorno de pánico, estrés postraumático o fobia social",
        "paciente_meta_ped": "Pacientes en manejo por neurociencias",
        "caracteristica": "Sertralina 50 mg en tabletas recubiertas con Sello de Bioequivalencia Comprobada",
        "beneficio": "garantiza idéntica biodisponibilidad y eficacia clínica que el innovador con costo accesible",
        "arg_imagen": "otorga la certeza clínica de prescribir una Sertralina con Bioequivalencia Comprobada",
        "arg_finanzas": "evita el abandono del tratamiento crónico gracias a su bioequivalencia accesible",
        "nicho_flanqueo": "pacientes crónicos que necesitan seguridad bioequivalente certificada",
        "love_brand": "Bioequivalencia comprobada para acompañar la recuperación emocional."
    },
    "MR FELICITAT": {
        "producto": "Felicitat",
        "clase_terapeutica": "Antidepresivos ISRS - Escitalopram (N06A)",
        "prioridad": 3,
        "apto_pediatria": False,
        "terminos_busqueda": ["FELICITAT", "ESCITALOPRAM", "LEXAPRO", "ANTIDEPRESIVO"],
        "paciente_meta": "Pacientes adultos con episodios depresivos mayores, trastorno de angustia o ansiedad generalizada",
        "paciente_meta_ped": "Pacientes en manejo de estado de ánimo",
        "caracteristica": "Escitalopram en presentaciones de 10 mg y 20 mg (30 tabletas recubiertas) con acción dual en el receptor SERT",
        "beneficio": "ofrece inhibición altamente selectiva de la recaptación de serotonina para una mejoría emocional sostenida",
        "arg_imagen": "alta selectividad serotoninérgica con excelente perfil de tolerabilidad",
        "arg_finanzas": "cajas completas de 30 tabletas en 10 mg y 20 mg que aseguran el mes completo de terapia",
        "nicho_flanqueo": "pacientes que requieren ajustar dosis entre 10 mg y 20 mg con excelente tolerabilidad",
        "love_brand": "Ayudar a miles de pacientes a volver a disfrutar de la vida."
    }
}

MARCAS_OFICIALES_GUTIS_NIC = [
    "GASTROALIVIO", "TALERDIN", "DALIVIO", "CONFLEXIL", "VALERPAN", "RENOVART", "BIOTOS",
    "CLEMBROXIL", "MOMETZONA", "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL",
    "ANSIOLIT", "DEPAX", "FELICITAT"
]

# CORREGIDO: Non-capturing group (?:...) para evitar UserWarning de pandas
import re
PATRON_REGEX_GUTIS = re.compile(r'\b(?:' + '|'.join(MARCAS_OFICIALES_GUTIS_NIC) + r')\b')

REGLAS_FARMA = """
REGLAS ESTRICTAS DE NEGOCIO Y VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026:
1. CERO EMOJIS: Prohibido utilizar emojis. Usa viñetas limpias, negritas y estructura ejecutiva.
2. CLASE TERAPÉUTICA COMPLETA: Cada marca de Gutis compite contra toda su clase terapéutica.
3. ADUANA VADEMÉCUM NICARAGUA 2026: Jamás menciones marcas ajenas a Nicaragua como 'Disflam', 'Conrelax', 'Dalivium', 'Valvirex' o 'Primabela'.
4. ESCALA DE ADOPCIÓN Y ESPECIALIDAD: En LEALTAD (>50% MS) agradece su respaldo como socio estratégico, blinda y haz PUENTE hacia una 2da marca. En PEDIATRÍA habla solo de pacientes pediátricos y presentaciones infantiles sin alcohol.
"""
