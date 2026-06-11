import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// OpenCode plugin entry for PowerPlatform-Core. This file lives at
// plugins/powerplatform-core/.opencode/plugins/, so the skills directory is two
// levels up. Registering it makes all the PowerPlatform-Core skills available.
//
// Note: `config.skills.paths` is the mechanism the superpowers plugin uses and is
// proven in practice, but it is not yet in OpenCode's official docs (see
// opencode issue #14370). If a future OpenCode version drops it, place or symlink
// plugins/powerplatform-core/skills under one of OpenCode's documented skills dirs
// (e.g. .opencode/skills) instead.
export const PowerPlatformCorePlugin = async ({ client, directory }) => {
  const skillsDir = path.resolve(__dirname, "../../skills");
  return {
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(skillsDir)) {
        config.skills.paths.push(skillsDir);
      }
    },
  };
};

export default PowerPlatformCorePlugin;
