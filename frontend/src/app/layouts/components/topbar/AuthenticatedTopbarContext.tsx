import {
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface AuthenticatedTopbarConfig {
  readonly desktopCenter?: ReactNode;
  readonly mobileAction?: ReactNode;
}

type AuthenticatedTopbarContextValue = {
  readonly config: AuthenticatedTopbarConfig | null;
  readonly setConfig: (config: AuthenticatedTopbarConfig | null) => void;
};

const AuthenticatedTopbarContext = createContext<AuthenticatedTopbarContextValue | null>(null);

export function AuthenticatedTopbarProvider({ children }: { readonly children: ReactNode }) {
  const [config, setConfig] = useState<AuthenticatedTopbarConfig | null>(null);
  const value = useMemo(
    () => ({
      config,
      setConfig,
    }),
    [config],
  );

  return <AuthenticatedTopbarContext.Provider value={value}>{children}</AuthenticatedTopbarContext.Provider>;
}

export function useAuthenticatedTopbarConfig(): AuthenticatedTopbarConfig | null {
  return useContext(AuthenticatedTopbarContext)?.config ?? null;
}

export function useConfigureAuthenticatedTopbar(config: AuthenticatedTopbarConfig | null) {
  const context = useContext(AuthenticatedTopbarContext);
  const lastAppliedConfigRef = useRef<AuthenticatedTopbarConfig | null>(null);

  useEffect(() => {
    if (!context) {
      return;
    }

    if (!areTopbarConfigsEqual(lastAppliedConfigRef.current, config)) {
      context.setConfig(config);
      lastAppliedConfigRef.current = config;
    }

  }, [context, config]);

  useEffect(() => {
    if (!context) {
      return;
    }

    return () => {
      context.setConfig(null);
      lastAppliedConfigRef.current = null;
    };
  }, [context]);
}

function areTopbarConfigsEqual(
  left: AuthenticatedTopbarConfig | null,
  right: AuthenticatedTopbarConfig | null,
) {
  if (left === right) return true;
  if (!left || !right) return false;
  return areReactNodesEqual(left.desktopCenter, right.desktopCenter) && areReactNodesEqual(left.mobileAction, right.mobileAction);
}

function areReactNodesEqual(left: ReactNode, right: ReactNode): boolean {
  if (left === right) return true;
  if (!isValidElement(left) || !isValidElement(right)) return false;
  if (left.type !== right.type || left.key !== right.key) return false;
  return arePropsEqual(left.props, right.props);
}

function arePropsEqual(left: Record<string, unknown>, right: Record<string, unknown>) {
  if (left === right) return true;
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) return false;
  for (const key of leftKeys) {
    if (!(key in right)) return false;
    const leftValue = left[key];
    const rightValue = right[key];

    if (isValidElement(leftValue) || isValidElement(rightValue)) {
      if (!areReactNodesEqual(leftValue as ReactNode, rightValue as ReactNode)) {
        return false;
      }
      continue;
    }

    if (!Object.is(leftValue, rightValue)) {
      return false;
    }
  }
  return true;
}
