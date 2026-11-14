import json
import streamlit as st
import streamlit.components.v1 as components

from components import charts, theme
from components.context import sidebar

# 1. Context & Theme Initialization
ctx = sidebar("overview")
t, rows = ctx["target"], ctx["rows"]
theme.apply_theme("overview")

# 2. Deep-Space Hero & Navigation Grid CSS
st.markdown(
    """
    <style>
    /* Full-Page Seamless Deep Space Canvas */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background: transparent !important;
    }
    .stApp {
        background:
            radial-gradient(circle at 74% 26%, rgba(28, 56, 108, 0.42) 0%, rgba(10, 17, 36, 0.25) 38%, transparent 70%),
            radial-gradient(ellipse at 20% 15%, rgba(16, 42, 76, 0.35) 0%, transparent 55%),
            linear-gradient(180deg, #03050c 0%, #060b18 42%, #050811 78%, #020307 100%) !important;
        color: #f8fafc;
    }

    /* Full-Viewport Twinkling Starfield Layer behind Hero & Page */
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 0;
        background-image:
            radial-gradient(1.5px 1.5px at 8% 12%, rgba(255,255,255,0.85), transparent),
            radial-gradient(1px 1px at 19% 28%, rgba(186,230,253,0.75), transparent),
            radial-gradient(2px 2px at 31% 9%, rgba(255,255,255,0.9), transparent),
            radial-gradient(1px 1px at 44% 22%, rgba(255,255,255,0.65), transparent),
            radial-gradient(1.5px 1.5px at 58% 14%, rgba(94,234,212,0.75), transparent),
            radial-gradient(1px 1px at 67% 34%, rgba(255,255,255,0.8), transparent),
            radial-gradient(2px 2px at 82% 11%, rgba(255,255,255,0.95), transparent),
            radial-gradient(1px 1px at 91% 29%, rgba(186,230,253,0.7), transparent),
            radial-gradient(1.5px 1.5px at 14% 46%, rgba(255,255,255,0.6), transparent),
            radial-gradient(1px 1px at 27% 58%, rgba(255,255,255,0.5), transparent),
            radial-gradient(1.5px 1.5px at 49% 44%, rgba(186,230,253,0.55), transparent),
            radial-gradient(1px 1px at 73% 52%, rgba(255,255,255,0.65), transparent),
            radial-gradient(1.5px 1.5px at 88% 48%, rgba(255,255,255,0.75), transparent),
            radial-gradient(1px 1px at 37% 72%, rgba(255,255,255,0.35), transparent),
            radial-gradient(1px 1px at 64% 78%, rgba(186,230,253,0.3), transparent);
        background-size: 100% 100%;
        mask-image: linear-gradient(180deg, rgba(0,0,0,1) 0%, rgba(0,0,0,0.85) 55%, rgba(0,0,0,0.15) 100%);
        -webkit-mask-image: linear-gradient(180deg, rgba(0,0,0,1) 0%, rgba(0,0,0,0.85) 55%, rgba(0,0,0,0.15) 100%);
    }

    /* Ensure content sits cleanly above starfield and iframe has zero box edges */
    [data-testid="stAppViewContainer"] > .main {
        position: relative;
        z-index: 1;
    }
    iframe[title="streamlit_components_v1.html_v1"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* Brand Logo & Hero Typography */
    .brand-lockup {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
    }
    .brand-icon {
        width: 54px;
        height: 54px;
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(45, 212, 191, 0.12));
        border: 1px solid rgba(56, 189, 248, 0.45);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 24px rgba(56, 189, 248, 0.25);
        flex-shrink: 0;
    }
    .brand-eyebrow {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #38bdf8;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .brand-title {
        font-size: 2.65rem;
        font-weight: 800;
        line-height: 1.08;
        background: linear-gradient(90deg, #ffffff 0%, #bae6fd 55%, #5eead4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .hero-subtitle {
        font-size: 1.05rem;
        line-height: 1.6;
        color: #cbd5e1;
        max-width: 560px;
        margin-bottom: 22px;
    }

    /* Compact Live Telemetry Strip inside Hero */
    .hero-telemetry {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 20px;
    }
    .ht-box {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-left: 3px solid #38bdf8;
        border-radius: 10px;
        padding: 10px 14px;
        backdrop-filter: blur(8px);
    }
    .ht-label {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #94a3b8;
        font-weight: 600;
    }
    .ht-val {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 2px;
    }
    .ht-sub {
        font-size: 0.74rem;
        color: #5eead4;
    }
    /* Section Header with Seamless Gradient Fade */
    .section-divider {
        margin-top: 24px;
        margin-bottom: 20px;
        padding-top: 26px;
        border-top: 1px solid transparent;
        border-image: linear-gradient(90deg, transparent 0%, rgba(56, 189, 248, 0.35) 50%, transparent 100%) 1;
    }
    .section-kicker {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: #38bdf8;
        font-weight: 700;
    }
    .section-heading {
        font-size: 1.45rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 2px 0 0 0;
    }

    /* 6 Rectangular Workspace Navigation Boxes */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(155deg, rgba(15, 23, 42, 0.85), rgba(9, 13, 24, 0.94)) !important;
        border: 1px solid rgba(56, 189, 248, 0.24) !important;
        border-radius: 14px !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(56, 189, 248, 0.75) !important;
        transform: translateY(-4px);
        box-shadow: 0 14px 32px rgba(56, 189, 248, 0.16) !important;
    }
    .nav-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }
    .nav-step {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.3);
        padding: 3px 9px;
        border-radius: 999px;
    }
    .nav-card-title {
        font-size: 1.18rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 6px 0 6px 0;
    }
    .nav-card-desc {
        font-size: 0.86rem;
        color: #94a3b8;
        line-height: 1.48;
        min-height: 58px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 3. Prepare Candidate Pins for the 3D Earth Globe
top = rows[0]
by_score = {r["id"]: r["total"] for r in rows}
globe_pins = [
    {
        "label": c["name"].split(" (")[0],
        "lat": float(c["lat"]),
        "lon": float(c["lon"]),
        "color": charts.sim_color(by_score.get(c["id"])) or "#38bdf8",
        "score": f"{by_score[c['id']]:.2f}" if by_score.get(c["id"]) is not None else "N/A",
    }
    for c in ctx["cand_list"]
]

# 4. HERO SECTION: Left Brand & Telemetry | Right Interactive 3D Earth in Space
hero_left, hero_right = st.columns([1.05, 1.25], gap="large", vertical_alignment="center")

with hero_left:
    # Celestial Cartographers Custom SVG Emblem + Brand Name
    st.markdown(
        """
        <div class="brand-lockup">
            <div class="brand-icon">
                <svg width="32" height="32" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="18" cy="18" r="12" stroke="#38bdf8" stroke-width="1.8"/>
                    <ellipse cx="18" cy="18" rx="16.5" ry="6.2" transform="rotate(-24 18 18)" stroke="#5eead4" stroke-width="1.5" stroke-dasharray="3 2"/>
                    <circle cx="18" cy="18" r="4" fill="#38bdf8" fill-opacity="0.35" stroke="#bae6fd" stroke-width="1.4"/>
                    <circle cx="29" cy="12" r="2.2" fill="#5eead4"/>
                </svg>
            </div>
            <div>
                <div class="brand-eyebrow">NASA Space Apps Challenge 2026</div>
                <h1 class="brand-title">Celestial Cartographers</h1>
            </div>
        </div>
        <p class="hero-subtitle">
            Discover worlds within our world. Identify terrestrial analogues that mirror lunar and Martian terrain,
            score environmental fidelity transparently, and pinpoint exactly where planetary analogies break down.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Active Mission Telemetry Cards
    st.markdown(
        f"""
        <div class="hero-telemetry">
            <div class="ht-box">
                <div class="ht-label">Active Planetary Target</div>
                <div class="ht-val">{t['name'].split(' (')[0]}</div>
                <div class="ht-sub">{t['body']} · {t['lat']:.2f}°, {t['lon']:.2f}°</div>
            </div>
            <div class="ht-box" style="border-left-color: #5eead4;">
                <div class="ht-label">Top Earth Analogue</div>
                <div class="ht-val">{top['name'].split(' (')[0]}</div>
                <div class="ht-sub">Similarity Index {top['total']:.2f}</div>
            </div>
            <div class="ht-box" style="border-left-color: #a78bfa;">
                <div class="ht-label">Mission Objective</div>
                <div class="ht-val">{ctx['objective']}</div>
                <div class="ht-sub">8-Dimension Weighting</div>
            </div>
            <div class="ht-box" style="border-left-color: #fb923c;">
                <div class="ht-label">Candidate Sites</div>
                <div class="ht-val">{len(rows)} Ranked</div>
                <div class="ht-sub">{len(st.session_state.get('discovered', []))} Newly Discovered</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Primary Quick-Launch CTA Buttons
    cta1, cta2 = st.columns(2)
    with cta1:
        if st.button("🎛️ Configure Mission Control", type="primary", use_container_width=True):
            st.switch_page("views/01_Mission_Control.py")
    with cta2:
        if st.button("🪐 Launch Planetary Explorer", use_container_width=True):
            st.switch_page("views/02_Planetary_Explorer.py")

with hero_right:
    # Interactive 3D Rotating Earth Globe (Three.js) with North Pole Up / South Pole Down & Starfield
    pins_json = json.dumps(globe_pins)
    globe_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: transparent !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        #globe-container {{
            width: 100%;
            height: 100%;
            position: relative;
            cursor: grab;
            background: transparent;
            /* Soft radial mask so outer star edges dissolve invisibly into the page */
            mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 58%, rgba(0,0,0,0) 96%);
            -webkit-mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 58%, rgba(0,0,0,0) 96%);
        }}
        #globe-container:active {{
                cursor: grabbing;
            }}
            .hud-overlay {{
                position: absolute;
                bottom: 14px;
                left: 16px;
                right: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                pointer-events: none;
                font-size: 11px;
                color: #94a3b8;
                background: rgba(6, 11, 24, 0.72);
                border: 1px solid rgba(56, 189, 248, 0.25);
                padding: 7px 12px;
                border-radius: 999px;
                backdrop-filter: blur(6px);
            }}
            .hud-dot {{
                display: inline-block;
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #4ade80;
                margin-right: 6px;
                box-shadow: 0 0 8px #4ade80;
            }}
            #tooltip {{
                position: absolute;
                display: none;
                pointer-events: none;
                background: rgba(9, 14, 28, 0.92);
                border: 1px solid #38bdf8;
                color: #f8fafc;
                padding: 6px 10px;
                border-radius: 8px;
                font-size: 12px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.6);
                z-index: 10;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        <div id="globe-container">
            <div id="tooltip"></div>
            <div class="hud-overlay">
                <span><span class="hud-dot"></span><b>EARTH ANALOGUE NETWORK</b> · N↑ / S↓ POLAR ALIGNMENT</span>
                <span>Drag to rotate · Scroll to zoom</span>
            </div>
        </div>

        <script>
            const container = document.getElementById('globe-container');
            const tooltip = document.getElementById('tooltip');
            const pinsData = {pins_json};

            // Scene & Camera (Y-axis points straight UP = North Pole Up, South Pole Down)
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.position.set(0, 0.45, 3.15);
            camera.up.set(0, 1, 0);

            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setClearColor(0x000000, 0);
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.appendChild(renderer.domElement);

        // Ambient Starfield Particles (blending into the full-page starfield)
        const starGeom = new THREE.BufferGeometry();
            const starCount = 1800;
            const starPos = new Float32Array(starCount * 3);
            for (let i = 0; i < starCount * 3; i += 3) {{
                const r = 18 + Math.random() * 45;
                const theta = Math.random() * Math.PI * 2;
                const phi = Math.acos(2 * Math.random() - 1);
                starPos[i] = r * Math.sin(phi) * Math.cos(theta);
                starPos[i + 1] = r * Math.cos(phi);
                starPos[i + 2] = r * Math.sin(phi) * Math.sin(theta);
            }}
            starGeom.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
            const starMat = new THREE.PointsMaterial({{ color: 0xe2e8f0, size: 0.09, transparent: true, opacity: 0.85 }});
            scene.add(new THREE.Points(starGeom, starMat));

            // Lighting
            scene.add(new THREE.AmbientLight(0x64748b, 1.35));
            const sunLight = new THREE.DirectionalLight(0xffffff, 1.45);
            sunLight.position.set(5, 3, 5);
            scene.add(sunLight);

            // Earth Group (Strictly North Pole +Y, South Pole -Y)
            const earthGroup = new THREE.Group();
            scene.add(earthGroup);

            const radius = 1.0;
            const earthGeo = new THREE.SphereGeometry(radius, 64, 64);

            // Procedural Fallback Canvas Texture + High-Res Earth Texture Loader
            const loader = new THREE.TextureLoader();
            loader.setCrossOrigin('anonymous');

            const earthMat = new THREE.MeshPhongMaterial({{
                color: 0xffffff,
                specular: new THREE.Color(0x1e3a5f),
                shininess: 18
            }});

            // Load NASA Blue Marble / Three.js Earth Day Map
            loader.load(
                'https://raw.githubusercontent.com/mrdoob/three.js/r128/examples/textures/planets/earth_atmos_2048.jpg',
                (tex) => {{
                    earthMat.map = tex;
                    earthMat.needsUpdate = true;
                }},
                undefined,
                () => {{
                    // Offline fallback: clean bathymetric blue & wireframe grid
                    earthMat.color = new THREE.Color(0x0c2d57);
                }}
            );

            loader.load(
                'https://raw.githubusercontent.com/mrdoob/three.js/r128/examples/textures/planets/earth_specular_2048.jpg',
                (specTex) => {{
                    earthMat.specularMap = specTex;
                    earthMat.needsUpdate = true;
                }}
            );

            const earthMesh = new THREE.Mesh(earthGeo, earthMat);
            earthGroup.add(earthMesh);

            // Subtle Latitude / Longitude Cartographic Graticule Overlay
            const wireGeo = new THREE.SphereGeometry(radius * 1.004, 24, 18);
            const wireMat = new THREE.MeshBasicMaterial({{
                color: 0x38bdf8,
                wireframe: true,
                transparent: true,
                opacity: 0.08
            }});
            earthGroup.add(new THREE.Mesh(wireGeo, wireMat));

            // Atmospheric Halo Rim
            const atmoGeo = new THREE.SphereGeometry(radius * 1.045, 48, 48);
            const atmoMat = new THREE.MeshBasicMaterial({{
                color: 0x38bdf8,
                transparent: true,
                opacity: 0.12,
                side: THREE.BackSide
            }});
            earthGroup.add(new THREE.Mesh(atmoGeo, atmoMat));

            // Polar Axis Indicator (North Pole Up / South Pole Down)
            const axisMat = new THREE.LineBasicMaterial({{ color: 0x5eead4, transparent: true, opacity: 0.45 }});
            const axisPts = [new THREE.Vector3(0, -1.25, 0), new THREE.Vector3(0, 1.25, 0)];
            const axisGeo = new THREE.BufferGeometry().setFromPoints(axisPts);
            earthGroup.add(new THREE.Line(axisGeo, axisMat));

            // Convert Lat/Lon to 3D Cartesian (Y = North Pole, -Y = South Pole)
            function latLonToVec3(lat, lon, r) {{
                const phi = (90 - lat) * (Math.PI / 180);
                const theta = (lon + 180) * (Math.PI / 180);
                return new THREE.Vector3(
                    -r * Math.sin(phi) * Math.cos(theta),
                     r * Math.cos(phi),
                     r * Math.sin(phi) * Math.sin(theta)
                );
            }}

            // Plot Terrestrial Analogue Pins on Globe
            const pinMeshes = [];
            pinsData.forEach((p) => {{
                const pos = latLonToVec3(p.lat, p.lon, radius * 1.015);
                const pinGeo = new THREE.SphereGeometry(0.022, 16, 16);
                const pinMat = new THREE.MeshBasicMaterial({{ color: p.color || '#5eead4' }});
                const pin = new THREE.Mesh(pinGeo, pinMat);
                pin.position.copy(pos);
                pin.userData = p;
                earthGroup.add(pin);
                pinMeshes.push(pin);
            }});

            // OrbitControls with Auto-Rotation & Polar Re-alignment
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.06;
            controls.enablePan = false;
            controls.minDistance = 1.65;
            controls.maxDistance = 5.0;
            controls.autoRotate = true;
            controls.autoRotateSpeed = 0.85; // West-to-East natural Earth spin

            let isUserInteracting = false;
            let resumeTimer = null;

            controls.addEventListener('start', () => {{
                isUserInteracting = true;
                controls.autoRotate = false;
                if (resumeTimer) clearTimeout(resumeTimer);
            }});

            controls.addEventListener('end', () => {{
                isUserInteracting = false;
                // Resume natural Earth spin & re-align North Pole up after 2.2s idle
                resumeTimer = setTimeout(() => {{
                    controls.autoRotate = true;
                }}, 2200);
            }});

            // Hover Tooltip for Analogue Pins
            const raycaster = new THREE.Raycaster();
            const mouse = new THREE.Vector2();

            container.addEventListener('mousemove', (e) => {{
                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

                raycaster.setFromCamera(mouse, camera);
                const hits = raycaster.intersectObjects(pinMeshes);
                if (hits.length > 0) {{
                    const d = hits[0].object.userData;
                    tooltip.style.display = 'block';
                    tooltip.style.left = (e.clientX - rect.left + 12) + 'px';
                    tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
                    tooltip.innerHTML = `<b>${{d.label}}</b><br/><span style="color:#5eead4;">Similarity: ${{d.score}}</span>`;
                }} else {{
                    tooltip.style.display = 'none';
                }}
            }});

            // Animation Loop
            function animate() {{
                requestAnimationFrame(animate);

                // Gently self-align camera latitude back toward upright North-up orientation when idle
                if (!isUserInteracting && controls.autoRotate) {{
                    const currentPolar = controls.getPolarAngle();
                    const targetPolar = Math.PI * 0.44; // Upright view with North Pole at top
                    const diff = targetPolar - currentPolar;
                    if (Math.abs(diff) > 0.002) {{
                        const dist = camera.position.distanceTo(controls.target);
                        const azim = controls.getAzimuthalAngle();
                        const nextPolar = currentPolar + diff * 0.025;
                        camera.position.x = dist * Math.sin(nextPolar) * Math.sin(azim);
                        camera.position.y = dist * Math.cos(nextPolar);
                        camera.position.z = dist * Math.sin(nextPolar) * Math.cos(azim);
                    }}
                }}

                controls.update();
                renderer.render(scene, camera);
            }}
            animate();

            window.addEventListener('resize', () => {{
                if (!container.clientWidth || !container.clientHeight) return;
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            }});
        </script>
    </body>
    </html>
    """
    components.html(globe_html, height=490)

# 5. SIX WORKSPACE NAVIGATION CARDS
st.markdown(
    """
    <div class="section-divider">
        <div class="section-kicker">Mission Architecture</div>
        <h2 class="section-heading">Explore Research & Engineering Workspaces</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

workspaces = [
    {
        "step": "Workspace 01",
        "icon": "🎛️",
        "title": "Mission Control",
        "desc": "Select target planetary worlds, define mission objectives, tune 8-dimensional scoring weights, and ingest custom raster layers.",
        "page": "views/01_Mission_Control.py",
        "btn": "Open Mission Control →",
    },
    {
        "step": "Workspace 02",
        "icon": "🪐",
        "title": "Planetary Explorer",
        "desc": "Fly over lunar and Martian targets in 3D, inspect orbital data layers, and generate quantitative environmental fingerprints.",
        "page": "views/02_Planetary_Explorer.py",
        "btn": "Launch Explorer →",
    },
    {
        "step": "Workspace 03",
        "icon": "🔍",
        "title": "Analog Discovery Lab",
        "desc": "Scan terrestrial elevation grids, detect geomorphological landforms automatically, and rank top analogue field sites.",
        "page": "views/03_Analog_Discovery_Lab.py",
        "btn": "Enter Discovery Lab →",
    },
    {
        "step": "Workspace 04",
        "icon": "⚖️",
        "title": "Scientific Comparison",
        "desc": "Compare Earth, Moon, and Mars sites side by side across mineralogical, thermal, and topographic fidelity metrics.",
        "page": "views/04_Scientific_Comparison.py",
        "btn": "Compare Worlds →",
    },
    {
        "step": "Workspace 05",
        "icon": "🦾",
        "title": "Mission Engineering",
        "desc": "Simulate rover traverses, slope hazards, subsurface drilling constraints, and operational safety envelopes.",
        "page": "views/05_Mission_Engineering.py",
        "btn": "Open Engineering →",
    },
    {
        "step": "Workspace 06",
        "icon": "📋",
        "title": "Field Campaign",
        "desc": "Compile transparent analogue validation briefs, document analogy breakdown limits, and export campaign reports.",
        "page": "views/06_Field_Campaign_Reports.py",
        "btn": "View Field Reports →",
    },
]

# Render 2 rows of 3 large rectangular navigation boxes
for row_idx in range(0, len(workspaces), 3):
    cols = st.columns(3, gap="medium")
    for col, ws in zip(cols, workspaces[row_idx : row_idx + 3]):
        with col:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="nav-card-header">
                        <span class="nav-step">{ws['step']}</span>
                        <span style="font-size:1.35rem;">{ws['icon']}</span>
                    </div>
                    <div class="nav-card-title">{ws['title']}</div>
                    <div class="nav-card-desc">{ws['desc']}</div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(ws["btn"], key=f"nav_{ws['page']}", use_container_width=True):
                    st.switch_page(ws["page"])

st.write("")
theme.demo_note()