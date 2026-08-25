#ifndef CADCAPTURE_ENGINE_CAPTUREPOLICY_H
#define CADCAPTURE_ENGINE_CAPTUREPOLICY_H

namespace cadcapture {

struct CapturePolicy
{
  bool allow_partial_capture;
  bool preserve_unknown_objects;
  bool enable_legacy_projection;
  bool validate_before_commit;

  CapturePolicy()
    : allow_partial_capture(true),
      preserve_unknown_objects(true),
      enable_legacy_projection(true),
      validate_before_commit(true)
  {
  }
};

}

#endif
