import type { EngineSpec } from "../contracts/evidence";
export default function EngineIdentity({
  role,
  engine,
}: {
  role: string;
  engine?: EngineSpec;
}) {
  return (
    <div className="min-w-0">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
        {role}
      </h3>
      <p className="mt-2 text-md">
        {engine?.label ?? "Checking engine identity…"}
      </p>
      {engine ? (
        <details className="mt-1">
          <summary className="min-h-11 cursor-pointer py-3 text-sm text-muted">
            Immutable engine identity
          </summary>
          <p className="break-all font-mono text-xs">
            {engine.commitSha}
            <br />
            {engine.imageDigest}
          </p>
        </details>
      ) : null}
    </div>
  );
}
