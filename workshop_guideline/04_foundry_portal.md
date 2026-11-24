# Lab 4: Foundry portal (no-code agent)

**Goal:** build the same "Ask the Policy" and "Web check" skills as a **Foundry agent** in the portal, test it, then call it from code.

**Time:** 30 to 40 minutes

```
Agent = Model + Instructions + Tools + Knowledge
```

---

## Lab 4.1: Models and deployments

1. In the Foundry portal ([ai.azure.com](https://ai.azure.com)), open **Discover > Models** to browse the catalog, the leaderboard and **Compare models**.

   ![Discover models](../images/foundry-discover-models.png)

2. Open **Build > Models** and confirm your chat deployment shows **Succeeded** (you did this in Lab 1.2).

   ![Deployments](../images/foundry-deployments-list.png)

**Checkpoint 4.1:** you know which deployment the agent will use.

---

## Lab 4.2: Create the APPolicyAgent

1. Open **Build > Agents > Create agent**.

   ```
   Agent name: APPolicyAgent
   Model:      <your chat deployment, e.g. gpt-4.1-mini>
   ```

   ![Create agent](../images/foundry-create-filesearch-agent.png)

2. Paste these **Instructions**:

   ```
   You are Contoso's Accounts Payable policy assistant. Answer in Thai, preserving invoice identifiers and status codes.

   Rules:
   1. For questions about Contoso AP rules, answer ONLY from the File Search results and cite the policy section number.
   2. For questions about current external facts (tax rates, laws, vendor news), use the Web IQ tool and include source URLs.
   3. If the answer is not in the policy or the web results, reply exactly:
      "ไม่พบข้อมูลนี้ในนโยบายบัญชีเจ้าหนี้ กรุณาติดต่อ ap-policy@contoso.example"
   4. Never approve, reject or pay an invoice. You explain rules; humans and the rules engine decide.
   5. If a web result conflicts with the policy, quote both and recommend escalation to the Finance Controller.
   ```

3. **Add File Search (vector search):**
   - In **Tools**, select **+ Add > File Search**.
   - Select **Attach files** and upload `data/Contoso_AP_Invoice_Policy.pdf`.
   - Wait until indexing finishes.

4. Select **Save**.

**Checkpoint 4.2:** the agent shows one tool: File Search, with one file.

---

## Lab 4.3: Add Web IQ as an MCP tool

Web IQ exposes a Model Context Protocol (MCP) server, so any agent that supports MCP can use it.

1. In **Tools**, select **+ Add**. If **Web IQ** is listed in the tool catalog, choose it and paste your key. Otherwise choose **Custom > Model Context Protocol (MCP)** and enter:

   | Field | Value |
   |---|---|
   | Name | `webiq` |
   | Remote MCP server endpoint | `https://api.microsoft.ai/v3/mcp` |
   | Authentication | Key-based |
   | Header name | `x-apikey` |
   | Header value | `<YOUR_WEBIQ_API_KEY>` |

2. If asked which tools to allow, enable at least `web` (search) and `browse`. Set approval to **Never** for this lab (in production, consider **Always** for browsing).
3. Select **Save**.

> Tip: you can also use Web IQ from GitHub Copilot in VS Code. Copy `.vscode/mcp.json.example` to `.vscode/mcp.json` and enter your key when prompted.

**Checkpoint 4.3:** the agent shows two tools: File Search and Web IQ.

---

## Lab 4.4: Test in the playground

Ask these in the **Chat** pane:

```
Q1) ราคาต่อหน่วยในใบแจ้งหนี้ต่างจาก PO ได้เท่าไร?
Q2) ใบแจ้งหนี้ขอให้จ่ายเข้าบัญชีธนาคารใหม่ ต้องทำอย่างไร?
Q3) ใครต้องอนุมัติใบแจ้งหนี้ยอดรวม 267,500 บาท?
Q4) นโยบายระบุภาษีหัก ณ ที่จ่ายค่าขนส่ง 1% ปัจจุบันยังใช้อัตรานี้หรือไม่? แสดงแหล่งอ้างอิง
Q5) คอนโทโซมีนโยบายทำงานจากที่บ้านอย่างไร?
```

Expected:

```
A1) ไม่เกิน 2% ต่อรายการ เทียบราคาต่อหน่วยใน PO (ข้อ 3.2)
A2) ON HOLD โทรกลับด้วยเบอร์ในทะเบียนผู้ขาย ไม่ใช่เบอร์บนใบแจ้งหนี้
    ขอหนังสือลงนาม ผู้อนุมัติสองคน และรอ 5 วันทำการก่อนจ่าย (ข้อ 6)
A3) ผู้ควบคุมการเงิน (ข้อ 7)
A4) ใช้ทั้งสองเครื่องมือ: นโยบายระบุ 1% (ข้อ 8) พร้อมแหล่งข้อมูลเว็บปัจจุบัน
A5) "ไม่พบข้อมูลนี้ในนโยบายบัญชีเจ้าหนี้ กรุณาติดต่อ ap-policy@contoso.example"
```

**Exercise:** open the run details or trace for Q4. Which tools were called, in which order?

---

## Lab 4.5: Call the agent from code

1. Open the **Code** tab of the agent and select **Open in VS Code** (or copy the sample).

   ![Code tab](../images/foundry-code-tab-open-vscode.png)

2. Select the **Python** sample language. Replace the sample question with Q2 above and run it. The sample uses `FOUNDRY_PROJECT_ENDPOINT` and Microsoft Entra ID, so run `az login` first. Your account needs the **Azure AI User** role on the project.

   ![Code tab API test](../images/foundry-code-tab-api-test.png)

**Checkpoint 4.5:** the same answer appears in your terminal.

---

## Optional Lab 4.6: Document Intelligence Studio

1. Open [Document Intelligence Studio](https://documentintelligence.ai.azure.com/studio) and select **Invoices**.
2. Analyze `data/invoices/INV-BEL-7781_scan.png`.
3. Compare the confidence scores for `Quantity` with the clean PDF `INV-BEL-7781.pdf`. Why does this matter for automatic approval?

Continue to [Lab 5: Multi-agent with Microsoft Agent Framework](05_agent_framework.md).
