---
title: Set up the Ciaren AI flow assistant and build a CSV flow
description: "Add a provider API key, describe a flow in plain language, review the proposal, run it and reverse the saved change in the Ciaren visual editor."
search: AI flow assistant setup add API key BYOK natural language build flow CSV tutorial activity history revert saved changes
---

# Set up the Ciaren AI flow assistant and build a CSV flow

Use a four-row CSV to try the full cycle. You will describe a change in plain language, inspect the proposed nodes, save the flow, run it yourself and use its activity history to reverse the change.

## Can Ciaren build a pipeline from a prompt?

Yes. Describe the result you want, and the assistant proposes real nodes, settings and connections for the whole flow: cleaning, joins, aggregations, date handling, data-quality checks, charts and, with the ML extension, features and models. You review the proposal and choose **Apply and save**, you choose when to run, and you can keep editing the flow by hand. The assistant works with your own API key from OpenAI, Anthropic or DeepSeek, and a model without tool calling gets a smaller set of guided plans.

[Flow assistant](flow-assistant.md#what-you-can-ask-for) lists example requests and what the assistant can and cannot create. Prefer to draw the workflow yourself? Follow the [manual quick start](quick-start.md).

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

## How do I add a provider API key?

Create a key in the console for the provider you intend to use. [OpenAI API keys](https://platform.openai.com/api-keys) · [Claude Console keys](https://platform.claude.com/settings/keys) · [DeepSeek API setup](https://api-docs.deepseek.com/) · [OpenCode Console authentication](https://opencode.ai/docs/console/api/inference#authentication).

Until a key is in use, the assistant panel shows **Connect a provider** with an **Open connections** button. You can also open **Connections** and choose **Add API key** under **Assistant API keys**. Name the key, choose the provider and a model, or pick **Other model…** to type a model ID that is not listed. Paste the key, confirm the storage notice and choose **Save key**. Ciaren keeps the key in this computer's OS keychain, and the first key you add is the one the assistant uses. With several keys, select the one to use; only one is in use at a time.

Use an API key issued for the selected service. A ChatGPT or Claude chat subscription does not supply an API key. For a direct DeepSeek key, choose **DeepSeek** and `deepseek-flash`. Provider calls may incur charges, so prefer a key with a spending limit. On a server without an OS keychain, such as a container, **Add API key** is disabled and an administrator configures a key with an environment variable or a mounted secret file. The [configuration reference](flow-assistant.md#deployment-and-credentials) covers exact names, precedence, rotation and disabling the assistant.

## Build a flow with a synthetic CSV

To build a flow, choose a project dataset on an empty canvas, describe the transformations and select **Create proposal**. The assistant generates the nodes and connections together. Review them before choosing **Apply and save**. **Run** executes the saved flow separately.

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
4. Review the proposed sequence: File Input → Limit Rows (10) → Remove Duplicates → File Output. Check the connections. A model can propose a different plan. If it does, choose **Regenerate**, revise the request with **Edit request**, or **Discard** it before saving.
5. Choose **Apply and save**. The nodes should now appear on the canvas, and a message offers **Undo** for a few seconds.
6. Close the assistant and click **Run**. On the successful run, select **File Output** and choose **Download output**. The CSV should contain three amounts: 2, 3 and 4, each once. Row order may vary.

The checks the assistant runs before you see a proposal use placeholder rows, so they confirm types and wiring, not your data. The run is where your real values are used.

For a larger example, follow [Train a shipping cost model from three CSVs](flow-assistant.md#train-a-shipping-cost-model-from-three-csvs). It uses two joins and evaluates a real model on held-out orders.

## Check the canvas and explain a node

Reload the editor page so the assistant panel returns to its opening screen. Open **Assistant**. The opening screen ends with a section marked **On device**. Choose **Check canvas** there to validate the wiring locally. Select a node on the canvas and choose **Explain selected node** to read its summary. Neither tool contacts a provider.

## Ask a question with a source

Choose **Assistant → Guides** and ask **How do I connect the two inputs of a Join?** Open the citation and compare its left and right handles with the [Join guide](../transformations/join.md). Guides searches English documentation bundled with the installed build. When it cannot find a supporting passage it can say so. No canvas or CSV rows accompany this question.

## How do I revert a saved change in activity history?

To revert a saved assistant change, open the flow’s **Assistant → Activity** history, choose **Show details** on the entry if you want to read it, and choose **Preview reversal**. Review the inverse, then choose **Confirm reversal**. Reload the flow to see both the original save and the reversal. On this example’s otherwise unchanged canvas the four added nodes disappear.

A reversal creates a new saved revision. The **Undo** button in the editor toolbar changes your local canvas instead. Save or discard pending edits before previewing a reversal. If another editor changes a setting involved in the reversal, keep your local work, compare the saved version and review a fresh preview. Reversing a flow does not run it or remove earlier run results.

## Change a flow you already have

On a flow that already has nodes, keep **Build** selected and describe the change, for example “Sort the amounts from high to low before the output.” The assistant sees the node types and connections of the canvas but not their current settings, so say what should change. The proposal lists the nodes it adds or updates and the connections it changes. The assistant can add nodes and change settings and connections, but it does not delete nodes that were already on the canvas. Remove those yourself.

## Troubleshoot a different result

- **No key, or Connect a provider.** Open **Connections → Assistant API keys** and check that a key is marked **In use** and enabled. A saved key needs `ciaren[keyring]` and an unlocked OS keychain. A headless server needs the environment or file source instead.
- **Missing dataset.** Check that the flow and CSV belong to the same project. Reopen the proposal if the input version has changed.
- **Save your changes first.** The assistant works from the saved flow. Choose **Save and send**, or save the canvas and send the request again.
- **Successful run with missing rows.** Try the [two-input Join repair walkthrough](flow-assistant.md#walkthrough-recover-a-missing-order). In Build, ask to keep the unmatched left rows, inspect the Join mode before saving, then run again to verify the output.
- **Run failed.** Choose **Diagnose** to look at the latest failed run. Diagnose proposes fixes only for a few cases, so describe a larger repair in Build.
- **This model cannot edit flows.** The selected model has no tool calling. Choose a tool-calling model in **Connections**.
- **Using your own agent.** Start with the [read-only Python SDK example](external-agent.md) for the node catalog.
