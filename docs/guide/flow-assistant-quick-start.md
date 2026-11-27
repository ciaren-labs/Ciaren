---
title: Set up the Ciaren AI flow assistant and build a CSV flow
description: "Register a provider API key, build a CSV cleanup flow, check its output and revert the saved change in the Ciaren visual editor."
search: AI flow assistant setup register API key BYOK CSV tutorial activity history revert saved changes
---

# Set up the Ciaren AI flow assistant and build a CSV flow

Use a four-row CSV to try the full review cycle. You will ask for a change, inspect the proposed nodes, save the flow, run it yourself and use its activity history to reverse the change.

## Can Ciaren build a pipeline from a prompt?

Yes. The assistant translates natural language to data workflows for supported CSV operations. It proposes real nodes and connections for a whole flow, including compatible two-input joins. You review and approve the proposal to save it, then choose when to run. The manual editor also supports operations outside the assistant’s plan.

Prefer to draw the workflow yourself? Follow the [manual quick start](quick-start.md).

## Open an editor with Assistant

Open a flow and look for **Assistant** in the toolbar. The published 0.3.1 release predates this feature. If the button is missing, build from a source revision that includes the assistant. With Git, Python 3.12+, an activated virtual environment and Node 24.15 or later in the 24.x series, build the editor and install the local package:

```sh
git clone https://github.com/ciaren-labs/Ciaren.git
cd Ciaren
npm ci --prefix frontend
npm run build --prefix frontend
python -m pip install "./backend[keyring]"
ciaren serve
```

Visit `http://127.0.0.1:8055`. The commands assume a new installation. For an existing database, back it up and run `ciaren db upgrade` before starting the upgraded server.

## How do I register a provider API key?

Create a key in the console for the provider you intend to use. [OpenAI API keys](https://platform.openai.com/api-keys) · [Claude Console keys](https://platform.claude.com/settings/keys) · [DeepSeek API setup](https://api-docs.deepseek.com/) · [OpenCode Console authentication](https://opencode.ai/docs/console/api/inference#authentication).

To set up or register a provider API key, open **Settings → Assistant**, choose your provider and save the setting. With the keyring source selected by the server, enter your provider-issued key in **New API key** and choose **Save key**. Look for **configured** and an empty key field. Checking this status makes no provider request.

Use an API key issued for the selected service. A ChatGPT or Claude chat subscription does not supply an API key. For a direct DeepSeek key, choose **DeepSeek** and `deepseek-flash`. Provider calls may incur charges. The server administrator can use an environment variable or a mounted secret file for headless installations. The [configuration reference](flow-assistant.md#deployment-and-credentials) covers exact names, precedence, rotation and disabling the assistant.

## Build a flow with a synthetic CSV

To build a CSV flow, choose a project dataset on an empty canvas, describe the transformations and select **Create proposal**. The assistant generates the nodes and connections together. Review them before choosing **Apply and save**. **Run** executes the saved flow separately.

1. Save the following text as `amounts.csv`:

   ```csv
   amount
   4
   3
   3
   2
   ```

2. Open **Datasets**, choose **Default** under **Upload to project** and upload the file. Go to **Flows → New flow**, choose **Blank flow**, name it **Amount cleanup** and use the same project.
3. Open **Assistant → Conversation → Build**. Choose `amounts.csv` under **Input dataset**. Leave column-name sharing off. Enter **Keep ten rows and remove duplicates** and choose **Create proposal**.
4. Review the proposed sequence: File Input → Limit Rows (10) → Remove Duplicates → File Output. Check the connections. A model can propose a different plan. If it does, close the proposal or revise the request before saving.
5. Choose **Apply and save**. The nodes should now appear on the canvas. Open **Assistant → Check canvas** to validate the wiring locally. Close the panel, select a node on the canvas and reopen **Assistant**. Use **Explain selected node** to read its bundled guide.
6. Close the assistant and click **Run**. On the successful run, select **File Output** and choose **Download output**. The CSV should contain three amounts: 2, 3 and 4, each once. Row order may vary.

For a larger example, follow [Train a shipping cost model from three CSVs](flow-assistant.md#train-a-shipping-cost-model-from-three-csvs). It uses two joins and evaluates a real model on held-out orders.

## Ask a question with a source

Choose **Assistant → Guides** and ask **How do I connect the two inputs of a Join?** Open the citation and compare its left and right handles with the [Join guide](../transformations/join.md). Guides searches English documentation bundled with the installed build. When it cannot find a supporting passage it can say so. No canvas or CSV rows accompany this question.

## How do I revert a saved change in activity history?

To revert a saved assistant change, open the flow’s **Assistant → Activity** history, expand the entry and choose **Preview reversal**. Review the inverse, then choose **Confirm reversal**. Reload the flow to see both the original save and the reversal. On this example’s otherwise unchanged canvas the four added nodes disappear.

A reversal creates a new saved revision. Undo changes your local canvas. Save or discard pending edits before previewing a reversal. If another editor changes a setting involved in the reversal, keep your local work, compare the saved version and review a fresh preview. Reversing a flow does not run it or remove earlier run results.

## Troubleshoot a different result

- **Missing or unavailable key.** Check the provider and source shown in Settings. An unavailable native keyring needs an unlocked supported backend or an explicitly configured environment or file source.
- **Missing dataset.** Check that the flow and CSV belong to the same project. Reopen the proposal if the input version has changed.
- **Successful run with missing rows.** Try the [two-input Join repair walkthrough](flow-assistant.md#walkthrough-recover-a-missing-order). Diagnose can propose keeping unmatched left rows. Inspect the Join mode before saving, then run again to verify the output.
- **Using your own agent.** Start with the [read-only Python SDK example](external-agent.md) for the node catalog.
