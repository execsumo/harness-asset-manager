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
    enableAll: "Enable all auto-maintenance",
    agents: {
      label: "Repair drifted Agent bindings",
      sub: "Fold an edited harness copy back into the store only when it is provably the only edit.",
    },
    skills: {
      label: "Adopt new local Skills",
      sub: "Adopt equivalent unmanaged Skill folders and replace them with store links.",
    },
    slash_commands: {
      label: "Adopt new slash commands",
      sub: "Adopt equivalent unmanaged command files without overwriting their contents.",
    },
    mcp: {
      label: "Adopt MCP configurations",
      sub: "Adopt only when all observed harness configurations are identical.",
    },
    hooks: {
      label: "Adopt Hooks",
      sub: "Promote equivalent unmanaged Hooks into the shared manifest.",
    },
    permissions: {
      label: "Adopt Permissions",
      sub: "Promote equivalent unmanaged deny rules into the shared manifest.",
    },
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
      enableAll: "启用全部自动维护",
      agents: {
        label: "自动修复偏离的 Agent 绑定",
        sub: "只有在能证明它是唯一编辑时，才将 harness 副本折叠回存储。",
      },
      skills: {
        label: "自动采用新的本地 Skill",
        sub: "采用内容相同的未托管 Skill 文件夹，并替换为存储链接。",
      },
      slash_commands: {
        label: "自动采用新的斜杠命令",
        sub: "采用内容相同的未托管命令文件，不覆盖其内容。",
      },
      mcp: {
        label: "自动采用 MCP 配置",
        sub: "只有所有 harness 配置完全一致时才采用。",
      },
      hooks: {
        label: "自动采用 Hooks",
        sub: "将内容相同的未托管 Hook 提升到共享清单。",
      },
      permissions: {
        label: "自动采用权限规则",
        sub: "将内容相同的未托管拒绝规则提升到共享清单。",
      },
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
