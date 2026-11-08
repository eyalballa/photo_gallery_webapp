import type { WallClient } from "./api/client";
import { PasscodeGate } from "./PasscodeGate";

export function App({ client }: { client: WallClient }) {
  return <PasscodeGate client={client} />;
}
