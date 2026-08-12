/**
 * 用途：在前端提供源模型扩展名提示；真实格式与处理路由仍由后端决定。
 */
export function isSupportedPartSourceFile(fileName: string): boolean {
  return /\.(step|stp|catpart|catproduct|zip)$/i.test(fileName)
}
