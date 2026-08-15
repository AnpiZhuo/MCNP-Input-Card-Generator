/**
 * volumeShader — WebGL2 光线步进体积渲染（契约 meshtal-visualization.md §4.7）
 *
 * ⚠️ 重要（真实渲染根因修复，2026-08-15）：shader 字符串**不得**以 `#version 300 es` 开头——
 * three r160 对 RawShaderMaterial 会先前置 `#define SHADER_TYPE …` 块再拼用户源码，
 * 若用户源码首行是 `#version`，编译报「#version directive must occur before anything else」，
 * 程序无效 → 体积层从未渲染（用户实测「只见栅元不见体积层」的真根因）。
 * 正确做法：shader 字符串不含 `#version`，材质设 `glslVersion: THREE.GLSL3`（= "300 es"），
 * 由 three 在最顶端生成 `#version 300 es`（版本指令必须是首行）。
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

export const RAY_MARCH_VERTEX = `precision highp float;
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

export const RAY_MARCH_FRAGMENT = `precision highp float;
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
  // 深度剥除（用户需求「拉低时外层先透明、内层慢慢跟」）：
  // 滑杆越低，每条光线靠近视线的外侧 peel 段按二次曲线平滑淡出（外层先透明），
  // 内层保持完整采样；整体再乘图层级透明度 uOpacity（内层慢慢跟着变淡）。
  // uOpacity=1 → peel=0、采样系数 m=1，行为与全不透明完全一致（零回归）。
  float peel = (1.0 - uOpacity) * 0.5;
  float spanT = max(t1 - t0, 1e-9);
  int steps = max(1, uSteps);
  float d = (t1 - t0) / float(steps);
  vec3 span = max(uBoxMax - uBoxMin, vec3(1e-9));
  vec4 acc = vec4(0.0);
  for (int i = 0; i < ${MAX_RAY_STEPS}; i++) {
    if (i >= steps) break;
    float s = t0 + (float(i) + 0.5) * d;
    float df = (s - t0) / spanT;
    float m = 1.0;
    if (peel > 0.0 && df < peel) {
      float k = clamp(df / max(peel, 1e-6), 0.0, 1.0);
      m = k * k;
    }
    vec3 pos = ro + rd * s;
    vec3 n = (pos - uBoxMin) / span;
    // 数据布局：numpy (x,y,z) 扁平（z 最快），DataTexture3D dims=(nk,nj,ni)
    // → 纹理坐标 = (z, y, x)，采样 uv 需 swizzle
    vec3 uvw = clamp(vec3(n.z, n.y, n.x), 0.0, 1.0);
    vec4 col = texture(uTex, uvw);
    float a = col.a * m;
    acc.rgb += (1.0 - acc.a) * col.rgb * a;
    acc.a += (1.0 - acc.a) * a;
    if (acc.a > 0.98) break;
  }
  // uOpacity 是【图层级】透明度：只乘最终 alpha（用户实测：若按每采样步乘，
  // 大网格 256 步累积后无论滑杆多低都近乎不透明，「调低透明度没用」）。
  // acc.rgb 为 front-to-back 预乘累积，NormalBlending 下与场景正确合成。
  fragColor = vec4(acc.rgb, acc.a * uOpacity);
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
 *
 * 关键（真实渲染修复）：RawShaderMaterial + `glslVersion: THREE.GLSL3` ——
 * shader 字符串不含 `#version`，由 three 在编译源最顶端生成 `#version 300 es`
 * （three 会给 RawShaderMaterial 前置 `#define SHADER_TYPE …` 块，`#version` 必须
 * 在其之前且为首行，故不能放在用户 shader 字符串里）。
 * 完整 uniform/属性声明由本 shader 自带（RawShaderMaterial 不做属性/varying 前缀转换）。
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
    glslVersion: THREE.GLSL3,
    transparent: true,
    depthWrite: false,
  });
}
