#ifndef CAD_PARSE_CAA_H
#define CAD_PARSE_CAA_H

#include "CadParseContracts.h"

#include <set>

class CATDocument;
class CATISpecObject;
class CATUnicodeString;

namespace cadparse
{
class SessionGuard
{
public:
  SessionGuard();
  ~SessionGuard();
  bool Open(std::string& error);

private:
  SessionGuard(const SessionGuard&);
  SessionGuard& operator=(const SessionGuard&);
  bool _open;
  std::string _name;
};

class DocumentGuard
{
public:
  DocumentGuard();
  ~DocumentGuard();
  bool OpenReadOnly(const std::string& path, std::string& error);
  CATDocument* Get() const;

private:
  DocumentGuard(const DocumentGuard&);
  DocumentGuard& operator=(const DocumentGuard&);
  CATDocument* _document;
};

class UniversalFeatureCrawler
{
public:
  UniversalFeatureCrawler(FeatureTypeRegistry& registry, ParseContext& context,
                          std::vector<FeatureRecord>& features,
                          std::vector<RelationRecord>& relations);
  bool Crawl(CATDocument* document, std::string& error);

private:
  std::string AddObject(INativeObjectView& view, const std::string& parent_id,
                        const std::string& tree_path);
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

void RegisterCoreDecoders(FeatureTypeRegistry& registry,
                          std::vector<IFeatureDecoder*>& owned_decoders);
void DeleteCoreDecoders(std::vector<IFeatureDecoder*>& owned_decoders);
std::string UnicodeToUtf8(const ::CATUnicodeString& value);
}

#endif
