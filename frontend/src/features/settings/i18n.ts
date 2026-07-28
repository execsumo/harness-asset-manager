import { useLocalizedCopy, type CopyShape, type LocalizedCopy } from "../../i18n";

const englishSettingsCopy = {
  title: "Settings",
  subtitle: "Local paths and per-harness discovery.",
  loading: "Loading settings",
  storage: {
    heading: "Local storage",
    storeTitle: "Harness Asset Manager store",
    storeSubtitle: "Canonical copies of skills in use live here.",
    cacheTitle: "Marketplace cache",
    cacheSubtitle: "Downloaded previews and install bundles.",
  },
  harnesses: {
    heading: "Harness roots",
    detected: "Detected on this machine",
    notDetected: "Not detected on this machine",
    enableSupport: (label: string) => `Enable ${label} support`,
    saving: "Saving...",
  },
  autoAdopt: {
    heading: "Automatic maintenance",
    label: "Repair drifted agent bindings automatically",
    sub: "When a harness replaces a managed agent link with its own copy, fold that copy back in — but only when it is provably the only edit. Conflicting edits are always left for you.",
  },
  errors: {
    unableToLoad: "Unable to load settings.",
    unableToUpdateHarnessSupport: "Unable to update harness support.",
  },
} as const;

export type SettingsCopy = CopyShape<typeof englishSettingsCopy>;

export const settingsCopy = {
  en: englishSettingsCopy,
  "zh-CN": {
    title: "设置",
    subtitle: "本地路径和每个 harness 的发现设置。",
    loading: "正在加载设置",
    storage: {
      heading: "本地存储",
      storeTitle: "Harness Asset Manager 存储",
      storeSubtitle: "使用中的 Skill 会以规范副本保存在这里。",
      cacheTitle: "商城缓存",
      cacheSubtitle: "已下载的预览和安装包。",
    },
    harnesses: {
      heading: "Harness 根目录",
      detected: "已在这台机器上检测到",
      notDetected: "未在这台机器上检测到",
      enableSupport: (label: string) => `启用 ${label} 支持`,
      saving: "保存中...",
    },
    autoAdopt: {
      heading: "自动维护",
      label: "自动修复偏离的 Agent 绑定",
      sub: "当 harness 用自己的副本替换托管的 Agent 链接时，将其折叠回存储中——但仅当其被证明是唯一的编辑时。冲突的编辑始终由您处理。",
    },
    errors: {
      unableToLoad: "无法加载设置。",
      unableToUpdateHarnessSupport: "无法更新 harness 支持状态。",
    },
  },
} satisfies LocalizedCopy<SettingsCopy>;

export function useSettingsCopy(): SettingsCopy {
  return useLocalizedCopy(settingsCopy);
}
