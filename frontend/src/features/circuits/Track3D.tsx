"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { buildTrackGeometry, BuiltTrackGeometry } from "./buildTrackGeometry";

interface CornerData {
  number: number;
  letter?: string;
  angle?: number;
  distance?: number;
  x?: number;
  y?: number;
}

interface TrackGeometryPayload {
  status: string;
  circuit_id: string;
  circuit_name: string;
  direction?: string;
  total_length_meters?: number;
  rotation?: number;
  x?: number[];
  y?: number[];
  z?: number[];
  corners?: CornerData[];
  reason?: string;
}

interface Track3DProps {
  geometry: TrackGeometryPayload;
  selectedCorner?: number | null;
  onSelectCorner?: (cornerNumber: number | null) => void;
  className?: string;
}

export default function Track3D({
  geometry,
  selectedCorner,
  onSelectCorner,
  className = "",
}: Track3DProps): React.JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const [exaggeration, setExaggeration] = useState<number>(3.0);
  const [is2DMode, setIs2DMode] = useState<boolean>(false);
  const [webGLSupported, setWebGLSupported] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      const canvas = document.createElement("canvas");
      return Boolean(canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
    } catch {
      return false;
    }
  });
  const [activeCorner, setActiveCorner] = useState<number | null>(selectedCorner ?? null);

  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | THREE.OrthographicCamera | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);

  // Check WebGL availability on mount
  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) {
        setWebGLSupported(false);
      }
    } catch {
      setWebGLSupported(false);
    }
  }, []);

  // Compute built geometry
  const builtGeometry = useMemo<BuiltTrackGeometry | null>(() => {
    if (!geometry.x || !geometry.y || geometry.x.length < 3) {
      return null;
    }
    return buildTrackGeometry(
      geometry.x,
      geometry.y,
      geometry.z,
      geometry.corners,
      {
        trackWidth: 14.0,
        elevationExaggeration: exaggeration,
      }
    );
  }, [geometry, exaggeration]);

  // Three.js Scene Setup & Render
  useEffect(() => {
    if (!webGLSupported || !builtGeometry || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x101318);

    // 2. Camera
    const maxDim = Math.max(builtGeometry.bounds.width, builtGeometry.bounds.height);
    const cameraDist = maxDim * 1.5;

    let camera: THREE.PerspectiveCamera | THREE.OrthographicCamera;
    if (is2DMode) {
      const aspect = width / height;
      const frustumSize = maxDim * 1.2;
      camera = new THREE.OrthographicCamera(
        (frustumSize * aspect) / -2,
        (frustumSize * aspect) / 2,
        frustumSize / 2,
        frustumSize / -2,
        1,
        10000
      );
      camera.position.set(0, 0, cameraDist);
      camera.up.set(0, 1, 0);
    } else {
      camera = new THREE.PerspectiveCamera(45, width / height, 1, 20000);
      camera.position.set(0, -cameraDist * 0.8, cameraDist * 0.9);
      camera.up.set(0, 0, 1);
    }
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // 3. Renderer
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setWebGLSupported(false);
      return;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    rendererRef.current = renderer;

    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    // 4. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enableRotate = !is2DMode;
    controls.maxPolarAngle = is2DMode ? 0 : Math.PI / 2.05; // Prevent flipping below ground
    controlsRef.current = controls;

    // 5. Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight1.position.set(cameraDist * 0.5, -cameraDist * 0.5, cameraDist);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x7090b0, 0.4);
    dirLight2.position.set(-cameraDist * 0.5, cameraDist * 0.5, -cameraDist * 0.2);
    scene.add(dirLight2);

    // 6. Ground Grid
    const gridSize = Math.round(maxDim * 1.8);
    const gridHelper = new THREE.GridHelper(gridSize, 40, 0x222a36, 0x161c24);
    gridHelper.rotation.x = Math.PI / 2; // Match Z-up orientation
    gridHelper.position.z = builtGeometry.bounds.minZ - 2;
    scene.add(gridHelper);

    // 7. Track Ribbon Mesh
    const ribbonBufferGeo = new THREE.BufferGeometry();
    ribbonBufferGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(builtGeometry.ribbon.vertices, 3)
    );
    ribbonBufferGeo.setAttribute(
      "normal",
      new THREE.BufferAttribute(builtGeometry.ribbon.normals, 3)
    );
    ribbonBufferGeo.setIndex(new THREE.BufferAttribute(builtGeometry.ribbon.indices, 1));

    const roadMaterial = new THREE.MeshStandardMaterial({
      color: 0x262b34,
      roughness: 0.82,
      metalness: 0.12,
      side: THREE.DoubleSide,
    });
    const roadMesh = new THREE.Mesh(ribbonBufferGeo, roadMaterial);
    scene.add(roadMesh);

    // 8. White Boundary Edge Lines
    const innerEdgeGeo = new THREE.BufferGeometry();
    innerEdgeGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(builtGeometry.innerEdge, 3)
    );
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0xffffff,
      linewidth: 2,
      transparent: true,
      opacity: 0.85,
    });
    const innerLine = new THREE.LineLoop(innerEdgeGeo, edgeMaterial);
    scene.add(innerLine);

    const outerEdgeGeo = new THREE.BufferGeometry();
    outerEdgeGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(builtGeometry.outerEdge, 3)
    );
    const outerLine = new THREE.LineLoop(outerEdgeGeo, edgeMaterial);
    scene.add(outerLine);

    // 9. Corner Markers
    const cornerMarkersGroup = new THREE.Group();
    const sphereGeo = new THREE.SphereGeometry(Math.max(4, maxDim * 0.007), 16, 16);

    builtGeometry.corners.forEach((corner) => {
      const isSelected = activeCorner === corner.number;
      const mat = new THREE.MeshStandardMaterial({
        color: isSelected ? 0xff3b30 : 0xe10600,
        emissive: isSelected ? 0x881008 : 0x440200,
        roughness: 0.4,
      });

      const sphere = new THREE.Mesh(sphereGeo, mat);
      sphere.position.set(corner.x, corner.y, corner.z);
      sphere.userData = { cornerNumber: corner.number, cornerData: corner };
      cornerMarkersGroup.add(sphere);
    });
    scene.add(cornerMarkersGroup);

    // 10. Click detection on Corner Markers
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handlePointerDown = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(cornerMarkersGroup.children);

      if (intersects.length > 0) {
        const hit = intersects[0].object;
        const cNum = hit.userData?.cornerNumber;
        if (cNum !== undefined) {
          setActiveCorner(cNum);
          if (onSelectCorner) onSelectCorner(cNum);
        }
      }
    };

    renderer.domElement.addEventListener("click", handlePointerDown);

    // 11. Animation Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // 12. Resize Handler
    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      if (is2DMode) {
        const ortho = cameraRef.current as THREE.OrthographicCamera;
        const aspect = w / h;
        const frustumSize = maxDim * 1.2;
        ortho.left = (frustumSize * aspect) / -2;
        ortho.right = (frustumSize * aspect) / 2;
        ortho.top = frustumSize / 2;
        ortho.bottom = frustumSize / -2;
        ortho.updateProjectionMatrix();
      } else {
        const persp = cameraRef.current as THREE.PerspectiveCamera;
        persp.aspect = w / h;
        persp.updateProjectionMatrix();
      }
      rendererRef.current.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // Cleanup
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("click", handlePointerDown);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [builtGeometry, is2DMode, webGLSupported, activeCorner, onSelectCorner]);

  const resetCamera = () => {
    if (!controlsRef.current || !cameraRef.current || !builtGeometry) return;
    const maxDim = Math.max(builtGeometry.bounds.width, builtGeometry.bounds.height);
    const cameraDist = maxDim * 1.5;

    if (is2DMode) {
      cameraRef.current.position.set(0, 0, cameraDist);
    } else {
      cameraRef.current.position.set(0, -cameraDist * 0.8, cameraDist * 0.9);
    }
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };

  // Compute dynamic 2D SVG viewBox from actual coordinates
  const svgViewBox = useMemo(() => {
    if (!geometry.x || !geometry.y || geometry.x.length < 3) {
      return { vb: "-2000 -2000 4000 4000", stroke: 12 };
    }
    const xs = geometry.x;
    const ys = geometry.y.map((y) => -y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const w = maxX - minX || 1000;
    const h = maxY - minY || 1000;
    const pad = Math.max(w, h) * 0.08;
    return {
      vb: `${minX - pad} ${minY - pad} ${w + 2 * pad} ${h + 2 * pad}`,
      stroke: Math.max(12, Math.round(Math.max(w, h) * 0.016)),
    };
  }, [geometry.x, geometry.y]);

  // Not available or missing geometry points
  if (geometry.status !== "ok" || !geometry.x || !geometry.y || geometry.x.length < 3) {
    return (
      <div className={`flex flex-col items-center justify-center p-8 bg-[var(--raised)] border border-[var(--border)] rounded-lg text-center min-h-[380px] ${className}`}>
        <div className="text-[12px] font-mono text-[var(--accent)] mb-2 uppercase font-bold">
          Track Layout Information
        </div>
        <p className="text-[13px] text-[var(--text-3)] max-w-md mb-5">
          {geometry.reason || "FastF1 position stream required for interactive 3D track render."}
        </p>
      </div>
    );
  }

  // WebGL Fallback - 2D SVG outline
  if (!webGLSupported) {
    return (
      <div className={`flex flex-col items-center justify-center p-8 bg-[var(--raised)] border border-[var(--border)] rounded-lg text-center min-h-[380px] ${className}`}>
        <div className="text-[12px] font-mono text-[var(--accent)] mb-2 uppercase font-bold">
          3D acceleration not available
        </div>
        <p className="text-[13px] text-[var(--text-3)] max-w-md mb-5">
          Your browser or graphics environment does not support WebGL. Displaying 2D circuit outline.
        </p>

        {/* 2D SVG Track Render with dynamic viewBox */}
        <div className="w-full max-w-[600px] flex flex-col items-center">
          <svg
            className="w-full h-72 border border-[var(--border)] rounded-lg bg-[#101318] p-4 shadow-inner"
            viewBox={svgViewBox.vb}
          >
            <polyline
              points={geometry.x.map((x, i) => `${x},${-geometry.y![i]}`).join(" ")}
              fill="none"
              stroke="#e10600"
              strokeWidth={svgViewBox.stroke}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-[11px] font-mono text-[var(--text-3)] mt-2">
            2D High-Precision Track Outline ({geometry.total_length_meters ? `${(geometry.total_length_meters / 1000).toFixed(3)} km` : "Scaled"})
          </span>
        </div>
      </div>
    );
  }

  const selectedCornerData = builtGeometry?.corners.find((c) => c.number === activeCorner);

  return (
    <div className={`relative flex flex-col rounded-lg border border-[var(--border)] bg-[#101318] overflow-hidden ${className}`}>
      {/* 3D Canvas Container */}
      <div ref={containerRef} className="w-full h-[520px] cursor-grab active:cursor-grabbing" />

      {/* Top Floating Controls */}
      <div className="absolute top-4 left-4 flex flex-wrap items-center gap-2 z-10">
        <button
          onClick={() => setIs2DMode((prev) => !prev)}
          className="px-3 py-1.5 rounded bg-[var(--surface)]/90 backdrop-blur border border-[var(--border)] text-[12px] font-mono text-[var(--text)] font-semibold hover:bg-[var(--raised)] transition"
        >
          {is2DMode ? "Switch to 3D Perspective" : "Top-Down 2D"}
        </button>

        <button
          onClick={resetCamera}
          className="px-3 py-1.5 rounded bg-[var(--surface)]/90 backdrop-blur border border-[var(--border)] text-[12px] font-mono text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--raised)] transition"
        >
          Reset Camera
        </button>
      </div>

      {/* Exaggeration Slider & Honest Limits Note */}
      <div className="absolute top-4 right-4 z-10 flex flex-col items-end gap-1 bg-[var(--surface)]/90 backdrop-blur border border-[var(--border)] p-2.5 rounded-lg text-right max-w-xs">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-[var(--text-3)]">Elevation Z:</span>
          <input
            type="range"
            min="1"
            max="8"
            step="0.5"
            value={exaggeration}
            onChange={(e) => setExaggeration(parseFloat(e.target.value))}
            className="w-24 accent-[#e10600]"
          />
          <span className="font-mono text-[12px] font-bold text-[var(--text)] w-8">
            {exaggeration}x
          </span>
        </div>
        <span className="text-[10px] text-[var(--text-3)] font-mono">
          Vertical scale exaggerated {exaggeration}x to reveal elevation gradients clearly.
        </span>
      </div>

      {/* Selected Corner Badge Panel */}
      {selectedCornerData && (
        <div className="absolute bottom-4 left-4 z-10 bg-[var(--surface)]/95 backdrop-blur border border-[var(--border)] p-3 rounded-lg flex items-center gap-4 text-xs font-mono">
          <div className="w-8 h-8 rounded bg-[#e10600] text-white font-bold flex items-center justify-center text-[14px]">
            T{selectedCornerData.number}
          </div>
          <div>
            <div className="font-bold text-[var(--text)]">
              Turn {selectedCornerData.number} {selectedCornerData.letter || ""}
            </div>
            <div className="text-[var(--text-3)] text-[11px]">
              Angle: {selectedCornerData.angle}° • Lap Distance: {Math.round(selectedCornerData.distance)}m
            </div>
          </div>
          <button
            onClick={() => {
              setActiveCorner(null);
              if (onSelectCorner) onSelectCorner(null);
            }}
            className="text-[var(--text-3)] hover:text-[var(--text)] ml-2 text-sm"
          >
            ✕
          </button>
        </div>
      )}

      {/* Bottom Direction & Dimension Strip */}
      <div className="px-4 py-2 border-t border-[var(--border)] bg-[var(--raised)] flex flex-wrap items-center justify-between text-[11px] font-mono text-[var(--text-3)]">
        <div>
          Direction:{" "}
          <span className="text-[var(--text)] font-semibold uppercase">
            {geometry.direction || "Clockwise"}
          </span>{" "}
          • Total Length:{" "}
          <span className="text-[var(--text)] font-semibold">
            {builtGeometry?.totalLength ? `${(builtGeometry.totalLength / 1000).toFixed(3)} km` : "n/a"}
          </span>
        </div>
        <div>
          Interactive 3D Ribbon • Left Drag to Rotate • Right Drag to Pan • Scroll to Zoom
        </div>
      </div>
    </div>
  );
}
