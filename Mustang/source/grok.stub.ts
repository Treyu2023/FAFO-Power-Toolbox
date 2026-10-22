/** Toolbox copy has no API key. The walkthrough on the page is the shop data. */
export async function askMustang(_input: {
  data: { partId: string; symptom: string; trans: "t5" | "4r70w" };
}): Promise<{ ok: false; error: string }> {
  return {
    ok: false,
    error:
      "The steps and the wire colors are already on this page. Ask Grok only runs in the online bay, so this toolbox copy does not send your reading anywhere.",
  };
}
