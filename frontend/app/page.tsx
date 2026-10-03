import { Suspense } from "react";
import Workspace from "../components/Workspace";
import { Loading } from "../components/ui";
export default function Page() {
  return (
    <Suspense
      fallback={
        <main className="content">
          <Loading label="Opening your workspace" />
        </main>
      }
    >
      <Workspace />
    </Suspense>
  );
}
