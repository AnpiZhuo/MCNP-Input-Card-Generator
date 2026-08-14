/**
 * volumeShader — WebGL2 光线步进体积渲染（契约 meshtal-visualization.md §4.7）
 *
 * - 前向光线步进（front-to-back 累积 alpha 合成）
 * - CPU 已上色（colorizeScalar RGBA，阈值以下 alpha 0）→ GPU 只采样 + alpha 合成
 * - 数据布局：后端 numpy (x,y,z) 扁平（z 最快），DataTexture3D dims=(nk,nj,ni)，
 *   纹理坐标 uv=(z,y,x)，采样时 swizzle `uvw.yzx`
 * - `isWebGL2()` feature-detect → 降级提示（DataTexture3D 需 WebGL2）
 *
 * shader 字符串快照测试锁防无意识改动。
 */
/** 最大光线步进数（uniform uSteps 上限，注入 shader 循环常量） */
export const MAX_RAY_STEPS = 256;

export const RAY_MARCH_VERTEX = `#version 300 es
precision highp float;
in vec3 position;
uniform mat4 modelViewMatrix;
uniform mat4 projectionMatrix;
uniform mat4 modelMatrix;
out vec3 vWorldPos;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const RAY_MARCH_FRAGMENT = `#version 300 es
precision highp float;
precision highp sampler3D;
in vec3 vWorldPos;
uniform sampler3D uTex;
uniform vec3 uBoxMin;
uniform vec3 uBoxMax;
uniform vec3 uCameraPos;
uniform float uOpacity;
uniform int uSteps;
out vec4 fragColor;

vec2 rayBox(vec3 ro, vec3 rd, vec3 bmin, vec3 bmax) {
  vec3 inv = 1.0 / rd;
  vec3 t0 = (bmin - ro) * inv;
  vec3 t1 = (bmax - ro) * inv;
  vec3 tmin = min(t0, t1);
  vec3 tmax = max(t0, t1);
  float tNear = max(max(tmin.x, tmin.y), tmin.z);
  float tFar = min(min(tmax.x, tmax.y), tmax.z);
  return vec2(tNear, tFar);
}

void main() {
  vec3 ro = uCameraPos;
  vec3 rd = normalize(vWorldPos - ro);
  vec2 t = rayBox(ro, rd, uBoxMin, uBoxMax);
  if (t.y < t.x || t.y < 0.0) {
    fragColor = vec4(0.0);
    return;
  }
  float t0 = max(t.x, 0.0);
  float t1 = t.y;
  int steps = max(1, uSteps);
  float d = (t1 - t0) / float(steps);
  vec3 span = max(uBoxMax - uBoxMin, vec3(1e-9));
  vec4 acc = vec4(0.0);
  for (int i = 0; i < ${MAX_RAY_STEPS}; i++) {
    if (i >= steps) break;
    float s = t0 + (float(i) + 0.5) * d;
    vec3 pos = ro + rd * s;
    vec3 n = (pos - uBoxMin) / span;
    // 数据布局：numpy (x,y,z) 扁平（z 最快），DataTexture3D dims=(nk,nj,ni)
    // → 纹理坐标 = (z, y, x)，采样 uv 需 swizzle
    vec3 uvw = clamp(vec3(n.z, n.y, n.x), 0.0, 1.0);
    vec4 col = texture(uTex, uvw);
    float a = col.a * uOpacity;
    acc.rgb += (1.0 - acc.a) * col.rgb * a;
    acc.a += (1.0 - acc.a) * a;
    if (acc.a > 0.98) break;
  }
  fragColor = acc;
}
`;

/** WebGL2 不可用降级提示（契约 §13 / §4.7） */
export const WEBGL2_UNAVAILABLE = "当前环境不支持 WebGL2 体积渲染（DataTexture3D 需要 WebGL2）";

/** WebGL2 feature-detect（非浏览器环境返回 false） */
export function isWebGL2(): boolean {
  try {
    if (typeof document === "undefined" || !document.createElement) return false;
    const canvas = document.createElement("canvas");
    if (!canvas || typeof canvas.getContext !== "function") return false;
    const gl = canvas.getContext("webgl2");
    return !!gl;
  } catch {
    return false;
  }
}

import * as THREE from "three";

export interface RayMarchMaterialOptions {
  texture: THREE.Data3DTexture;
  opacity?: number;
  boxMin?: [number, number, number];
  boxMax?: [number, number, number];
}

/**
 * 构建光线步进 RawShaderMaterial（CPU 已上色 → 采样 + alpha 合成）。
 * 用 RawShaderMaterial：shader 自带 `#version 300 es` + 完整 uniform/属性声明，
 * three 不会自动前缀（避免双 `#version` 编译错误）。
 * 由 VolumeRenderer 注入 texture/box/camera 相关 uniform 更新。
 */
export function buildRayMarchMaterial(opts: RayMarchMaterialOptions): THREE.RawShaderMaterial {
  return new THREE.RawShaderMaterial({
    uniforms: {
      uTex: { value: opts.texture },
      uBoxMin: { value: opts.boxMin ? new THREE.Vector3(...opts.boxMin) : new THREE.Vector3(-1, -1, -1) },
      uBoxMax: { value: opts.boxMax ? new THREE.Vector3(...opts.boxMax) : new THREE.Vector3(1, 1, 1) },
      uCameraPos: { value: new THREE.Vector3(0, 0, 0) },
      uOpacity: { value: opts.opacity ?? 1.0 },
      uSteps: { value: 128 },
    },
    vertexShader: RAY_MARCH_VERTEX,
    fragmentShader: RAY_MARCH_FRAGMENT,
    transparent: true,
    depthWrite: false,
  });
}
