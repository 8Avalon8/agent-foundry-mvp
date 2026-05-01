# LLM Dry Run Review Report

## Summary

这是由 Mock LLM 生成的 review dry run。它展示了 LLM Provider 接入后的产物形态。

## Findings

### F001 [medium] 示例风险：边界检查可能不足

- 证据：mock 根据 diff 文本生成
- 建议：补充边界输入测试，并确认上游保证。
