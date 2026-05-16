import { useEffect, useRef } from "react";
import * as THREE from "three";

export function ParticleCanvas({ pnl = 0 }) {
  const mountRef = useRef(null);
  const pnlRef = useRef(pnl);

  useEffect(() => {
    pnlRef.current = pnl;
  }, [pnl]);

  useEffect(() => {
    const mount = mountRef.current;
    const w = mount.clientWidth;
    const h = mount.clientHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 1000);
    camera.position.z = 80;

    const COUNT = 1200;
    const positions = new Float32Array(COUNT * 3);
    const velocities = [];

    for (let i = 0; i < COUNT; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 180;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 100;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 80;
      velocities.push({
        x: (Math.random() - 0.5) * 0.06,
        y: (Math.random() - 0.5) * 0.04,
        z: (Math.random() - 0.5) * 0.02,
      });
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.6,
      color: pnlRef.current >= 0 ? 0x00ff88 : 0xff4455,
      transparent: true,
      opacity: 0.6,
    });

    const points = new THREE.Points(geo, mat);
    scene.add(points);

    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      const pos = geo.attributes.position.array;
      for (let i = 0; i < COUNT; i++) {
        pos[i * 3] += velocities[i].x;
        pos[i * 3 + 1] += velocities[i].y;
        pos[i * 3 + 2] += velocities[i].z;
        if (Math.abs(pos[i * 3]) > 90) velocities[i].x *= -1;
        if (Math.abs(pos[i * 3 + 1]) > 50) velocities[i].y *= -1;
        if (Math.abs(pos[i * 3 + 2]) > 40) velocities[i].z *= -1;
      }
      geo.attributes.position.needsUpdate = true;
      points.rotation.y += 0.0008;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }}
    />
  );
}
