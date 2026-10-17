import { RoundedBox } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useEffect, useRef, useState } from 'react'
import { MathUtils, type Group, type Mesh, type MeshStandardMaterial } from 'three'

/**
 * The /login 3D hero: translucent frosted "time blocks" arranged like a schedule
 * column, with one accent block gliding into a gap (the product metaphor — an
 * emergency inserted into a full day). Pointer parallax, DPR capped at 1.5, render
 * loop paused when the tab is hidden. Lazy-loaded as its own chunk by LoginPage.
 *
 * Colours are literal brand hex (a WebGL scene can't read CSS tokens); they mirror
 * the dark-mode brand values in tokens.css.
 */

const BLOCKS = [
  { y: 1.7, color: '#2DD4BF', opacity: 0.26 },
  { y: 0.85, color: '#5EEAD4', opacity: 0.2 },
  { y: -0.85, color: '#2DD4BF', opacity: 0.2 },
  { y: -1.7, color: '#5EEAD4', opacity: 0.26 },
]

function Scene() {
  const group = useRef<Group>(null)
  const emergency = useRef<Mesh>(null)
  const t = useRef(0)

  useFrame((state, delta) => {
    if (group.current) {
      group.current.rotation.y = MathUtils.lerp(group.current.rotation.y, state.pointer.x * 0.25, 0.05)
      group.current.rotation.x = MathUtils.lerp(group.current.rotation.x, -state.pointer.y * 0.12, 0.05)
    }
    // 6s gentle loop: glide in from the right, hold, fade out, repeat.
    t.current = (t.current + delta) % 6
    const c = t.current / 6
    if (emergency.current) {
      const inPhase = Math.min(c / 0.35, 1)
      const outPhase = c > 0.88 ? (c - 0.88) / 0.12 : 0
      emergency.current.position.x = MathUtils.lerp(4.5, 0, inPhase) + outPhase * 4.5
      const mat = emergency.current.material as MeshStandardMaterial
      mat.opacity = 0.55 * inPhase * (1 - outPhase)
    }
  })

  return (
    <group ref={group}>
      {BLOCKS.map((b, i) => (
        <RoundedBox key={i} args={[3.2, 0.62, 0.3]} radius={0.09} smoothness={3} position={[0, b.y, 0]}>
          <meshStandardMaterial color={b.color} transparent opacity={b.opacity} roughness={0.3} metalness={0.1} />
        </RoundedBox>
      ))}
      <RoundedBox ref={emergency} args={[3.2, 0.62, 0.3]} radius={0.09} smoothness={3} position={[4.5, 0, 0]}>
        <meshStandardMaterial
          color="#14B8A6"
          transparent
          opacity={0}
          roughness={0.2}
          metalness={0.15}
          emissive="#0E7C86"
          emissiveIntensity={0.35}
        />
      </RoundedBox>
    </group>
  )
}

export default function Hero3D() {
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    const onVis = () => setPaused(document.hidden)
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 7], fov: 45 }}
      frameloop={paused ? 'never' : 'always'}
      gl={{ antialias: true, alpha: true }}
      style={{ background: 'transparent' }}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} intensity={1.1} />
      <pointLight position={[-4, -2, 3]} intensity={0.9} color="#2DD4BF" />
      <Scene />
    </Canvas>
  )
}
