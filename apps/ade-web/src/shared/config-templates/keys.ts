export const configTemplateKeys = {
  root: () => ["config-templates"] as const,
  list: () => [...configTemplateKeys.root(), "list"] as const,
};
