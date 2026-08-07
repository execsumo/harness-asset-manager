import { useLocalizedCopy, type CopyShape, type LocalizedCopy } from "../../i18n";

const englishActivityCopy = {
  title: "Activity",
  subtitle: "Recent changes made by Harness Asset Manager, the CLI, and automatic repair.",
  loading: "Loading recent activity",
  unableToLoad: "Unable to load recent activity.",
  emptyTitle: "No activity yet",
  emptyBody: "Changes will appear here after Harness Asset Manager updates a managed asset or configuration.",
  details: "Details",
  parameters: "Parameters",
  changedPaths: "Changed paths",
  noPathsChanged: "No filesystem paths changed.",
  errorType: "Error type",
  outcomes: {
    succeeded: "Succeeded",
    partial: "Partial",
    refused: "Refused",
    failed: "Failed",
  },
} as const;

export type ActivityCopy = CopyShape<typeof englishActivityCopy>;

export const activityCopy = {
  en: englishActivityCopy,
  "zh-CN": {
    title: "活动",
    subtitle: "Harness Asset Manager、CLI 和自动修复最近执行的更改。",
    loading: "正在加载最近活动",
    unableToLoad: "无法加载最近活动。",
    emptyTitle: "暂无活动",
    emptyBody: "Harness Asset Manager 更新托管资产或配置后，更改将显示在这里。",
    details: "详情",
    parameters: "参数",
    changedPaths: "更改的路径",
    noPathsChanged: "没有文件系统路径发生更改。",
    errorType: "错误类型",
    outcomes: {
      succeeded: "成功",
      partial: "部分成功",
      refused: "已拒绝",
      failed: "失败",
    },
  },
} satisfies LocalizedCopy<ActivityCopy>;

export function useActivityCopy(): ActivityCopy {
  return useLocalizedCopy(activityCopy);
}
