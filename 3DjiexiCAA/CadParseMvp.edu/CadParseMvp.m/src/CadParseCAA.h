// 本文件声明 CATIA V5R21 适配层：Session/Document RAII、原生对象遍历和 Decoder 工厂。
// CAA 类型只以前置声明和裸指针出现在适配边界，纯数据模块无需包含 CAA 头文件。
#ifndef CAD_PARSE_CAA_H
#define CAD_PARSE_CAA_H

#include "CadParseContracts.h"

#include <set>

class CATDocument;
class CATISpecObject;
class CATUnicodeString;

namespace cadparse
{
// CATIA Session 的 C++03 RAII 守卫。
// Open 成功后由本对象持有 Session 生命周期，析构时负责配对删除。
class SessionGuard
{
public:
  // 用途：创建尚未打开 Session 的守卫。
  SessionGuard();
  // 用途：若 Session 已打开，则在作用域结束时调用 R21 清理接口。
  ~SessionGuard();
  // 用途：创建本解析器使用的 CATIA Session；失败时返回 false 并填写 error。
  bool Open(std::string& error);

private:
  // 用途：禁止复制 Session 所有者，避免两个对象重复清理同一 Session；只声明不实现是 C++03 惯用法。
  SessionGuard(const SessionGuard&);
  // 用途：禁止 SessionGuard 赋值，保持 Session 所有权唯一。
  SessionGuard& operator=(const SessionGuard&);
  bool _open;
  std::string _name;
};

// CATDocument 的 C++03 RAII 守卫；只读打开的文档在析构时统一关闭并释放。
class DocumentGuard
{
public:
  // 用途：创建尚未持有文档的守卫。
  DocumentGuard();
  // 用途：关闭并释放当前持有的 CATDocument，允许所有提前返回路径安全退出。
  ~DocumentGuard();
  // 用途：按只读语义打开 CATPart；成功后守卫取得文档清理责任。
  bool OpenReadOnly(const std::string& path, std::string& error);
  // 用途：返回借用的 CATDocument 指针供遍历使用；调用者不得 Release 或长期保存。
  CATDocument* Get() const;

private:
  // 用途：禁止复制文档所有者，防止重复关闭同一个 CATDocument。
  DocumentGuard(const DocumentGuard&);
  // 用途：禁止 DocumentGuard 赋值，保持文档清理责任唯一。
  DocumentGuard& operator=(const DocumentGuard&);
  CATDocument* _document;
};

// 从文档根开始遍历本机 R21 公开接口可达对象，并保证每个枚举对象先产生基础 IR 记录。
class UniversalFeatureCrawler
{
public:
  // 用途：把本次遍历所需 Registry、上下文和输出容器以引用方式绑定到 Crawler。
  // 这些对象由调用方拥有，并且必须比 Crawler 活得更久。
  UniversalFeatureCrawler(FeatureTypeRegistry& registry, ParseContext& context,
                          std::vector<FeatureRecord>& features,
                          std::vector<RelationRecord>& relations);
  // 用途：扫描 document 的已验证入口；文档级致命失败返回 false，对象级失败记录诊断后继续。
  bool Crawl(CATDocument* document, std::string& error);

private:
  // 用途：为一个已适配对象分配稳定 ID、执行 Decoder、更新统计并建立 contains 关系。
  std::string AddObject(INativeObjectView& view, const std::string& parent_id,
                        const std::string& tree_path);
  // 用途：递归访问一个 CATISpecObject；visited 集合阻止循环引用导致无限递归。
  // spec 是借用指针，函数不接管其引用计数。
  bool VisitSpec(CATISpecObject* spec, const std::string& parent_id,
                 const std::string& parent_path);

  FeatureTypeRegistry& _registry;
  ParseContext& _context;
  std::vector<FeatureRecord>& _features;
  std::vector<RelationRecord>& _relations;
  FeatureIdGenerator _ids;
  std::set<CATISpecObject*> _visited;
  UnknownTypeCollector _unknown_types;
  FeatureTypeCatalog _catalog;
};

// 用途：创建并注册本轮已验证的基础 Typed Decoder。
// 新对象指针放入 owned_decoders，把 delete 责任明确交给调用方。
void RegisterCoreDecoders(FeatureTypeRegistry& registry,
                          std::vector<IFeatureDecoder*>& owned_decoders);
// 用途：逐个 delete 工厂创建的 Decoder，并清空所有权容器。
void DeleteCoreDecoders(std::vector<IFeatureDecoder*>& owned_decoders);
// 用途：使用 R21 CATUnicodeString API 把 CATIA 文本转换成 UTF-8 std::string。
std::string UnicodeToUtf8(const ::CATUnicodeString& value);
}

#endif
