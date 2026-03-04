import { eventTrigger } from "@trigger.dev/sdk";
import { logger } from "@trigger.dev/sdk";
import { createClient } from "@supabase/supabase-js";
import { z } from "zod";

interface HouseholdData {
  id: string;
  household_name: string;
  primary_contact_name: string;
  aum_usd: number;
  engagement_score: number;
  engagement_cohort: string;
  last_review_date: string;
}

interface Position {
  id: string;
  symbol: string;
  position_name: string;
  quantity: number;
  current_value_usd: number;
  unrealized_gain_loss_pct: number;
  sector: string;
  asset_class: string;
  weight_pct: number;
}

interface Account {
  id: string;
  account_name: string;
  total_value_usd: number;
  accounts: Position[];
}

const BriefingGenerationPayloadSchema = z.object({
  household_id: z.string().uuid(),
  trigger_source: z.enum(["crm_daily_sync", "review_reminder", "manual"]).optional(),
  force_regenerate: z.boolean().optional(),
  position_changes: z.array(z.object({
    symbol: z.string(),
    quantity_before: z.number().optional(),
    quantity_after: z.number().optional(),
  })).optional(),
});

type BriefingGenerationPayload = z.infer<typeof BriefingGenerationPayloadSchema>;

export const briefingGeneration = eventTrigger({
  name: "briefing_generation",
  schema: BriefingGenerationPayloadSchema,
  onSuccess: async (event, { ctx }) => {
    const supabase = createClient(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );

    const { household_id, trigger_source = "manual", force_regenerate = false, position_changes = [] } = event.payload;

    logger.info(`Starting briefing generation for household: ${household_id}`, {
      trigger_source,
      force_regenerate,
    });

    try {
      // Step 1: Fetch household data
      const { data: household, error: householdError } = await supabase
        .from("households")
        .select("*")
        .eq("id", household_id)
        .single();

      if (householdError || !household) {
        throw new Error(`Household not found: ${household_id}`);
      }

      logger.info(`Retrieved household: ${household.household_name}`, {
        aum: household.aum_usd,
        engagement_score: household.engagement_score,
      });

      // Step 2: Fetch all members of the household
      const { data: members, error: membersError } = await supabase
        .from("household_members")
        .select("*")
        .eq("household_id", household_id);

      if (membersError) {
        throw new Error(`Failed to fetch household members: ${membersError.message}`);
      }

      logger.info(`Retrieved ${members?.length || 0} household members`);

      // Step 3: Fetch all accounts and positions
      const { data: accounts, error: accountsError } = await supabase
        .from("accounts")
        .select("*")
        .eq("household_id", household_id);

      if (accountsError) {
        throw new Error(`Failed to fetch accounts: ${accountsError.message}`);
      }

      logger.info(`Retrieved ${accounts?.length || 0} accounts`);

      // Step 4: Fetch positions for each account
      const accountsWithPositions = await Promise.all(
        (accounts || []).map(async (account) => {
          const { data: positions, error: positionsError } = await supabase
            .from("positions")
            .select("*")
            .eq("account_id", account.id);

          if (positionsError) {
            logger.warn(`Failed to fetch positions for account ${account.id}`, {
              error: positionsError.message,
            });
            return { ...account, positions: [] };
          }

          return { ...account, positions: positions || [] };
        })
      );

      logger.info(`Retrieved positions across all accounts`);

      // Step 5: Compute deltas from last review
      const lastReviewDate = household.last_review_date
        ? new Date(household.last_review_date)
        : new Date(Date.now() - 365 * 24 * 60 * 60 * 1000); // Default to 1 year ago

      const positionDeltas = computePositionDeltas(accountsWithPositions, position_changes, lastReviewDate);

      logger.info(`Computed ${positionDeltas.length} position changes since last review`, {
        lastReviewDate: lastReviewDate.toISOString(),
      });

      // Step 6: Score engagement
      const engagementScore = await scoreEngagement(supabase, household, members);

      logger.info(`Engagement score calculated: ${engagementScore.overall}`, {
        components: engagementScore.components,
      });

      // Step 7: Generate conversation starters
      const conversationStarters = generateConversationStarters(
        household,
        accountsWithPositions,
        positionDeltas,
        engagementScore,
        members
      );

      logger.info(`Generated ${conversationStarters.length} conversation starters`);

      // Step 8: Assemble briefing content
      const briefingContent = assembleBriefingContent(
        household,
        members,
        accountsWithPositions,
        positionDeltas,
        engagementScore,
        conversationStarters
      );

      const briefingMarkdown = generateBriefingMarkdown(briefingContent);
      const briefingHtml = generateBriefingHtml(briefingContent);

      logger.info(`Generated briefing content (${briefingMarkdown.length} chars markdown)`);

      // Step 9: Save briefing to Supabase
      const { data: savedBriefing, error: briefingError } = await supabase
        .from("briefings")
        .insert({
          household_id,
          briefing_content: briefingContent,
          briefing_markdown: briefingMarkdown,
          briefing_html: briefingHtml,
          portfolio_summary: {
            total_aum: household.aum_usd,
            account_count: accountsWithPositions.length,
            asset_allocation: computeAssetAllocation(accountsWithPositions),
            ytd_performance: computePortfolioPerformance(accountsWithPositions),
          },
          position_changes: positionDeltas,
          engagement_score_snapshot: engagementScore.overall,
          engagement_cohort_snapshot: engagementScore.cohort,
          attrition_risk_snapshot: household.attrition_risk,
          conversation_starters: conversationStarters,
          recommended_actions: generateRecommendedActions(positionDeltas, engagementScore, household),
        })
        .select()
        .single();

      if (briefingError) {
        throw new Error(`Failed to save briefing: ${briefingError.message}`);
      }

      logger.info(`Briefing saved successfully`, { briefing_id: savedBriefing.id });

      // Step 10: Notify advisor (optional - can be handled separately)
      if (trigger_source === "crm_daily_sync" || trigger_source === "review_reminder") {
        await notifyAdvisor(supabase, household, savedBriefing);
      }

      logger.info(`Briefing generation completed successfully`, {
        briefing_id: savedBriefing.id,
        household: household.household_name,
      });

      return {
        success: true,
        briefing_id: savedBriefing.id,
        household_name: household.household_name,
        engagement_score: engagementScore.overall,
      };
    } catch (error) {
      logger.error(`Briefing generation failed`, {
        household_id,
        error: error instanceof Error ? error.message : String(error),
      });

      // Log error to sync_logs for audit trail
      await supabase.from("sync_logs").insert({
        organization_id: process.env.ORG_ID,
        sync_type: "briefing_generation",
        status: "failed",
        error_message: error instanceof Error ? error.message : String(error),
        records_processed: 1,
        records_failed: 1,
      });

      throw error;
    }
  },
});

function computePositionDeltas(
  accountsWithPositions: Array<{ id: string; total_value_usd: number; positions: Position[] }>,
  externalChanges: Array<{ symbol: string; quantity_before?: number; quantity_after?: number }>,
  lastReviewDate: Date
): Array<{ symbol: string; change_type: string; quantity_delta: number; value_delta: number; rationale: string }> {
  const deltas = [];

  // Process externally provided changes (from position_history)
  for (const change of externalChanges) {
    if (change.quantity_before !== undefined && change.quantity_after !== undefined) {
      const quantityDelta = change.quantity_after - change.quantity_before;
      deltas.push({
        symbol: change.symbol,
        change_type: quantityDelta > 0 ? "increase" : "decrease",
        quantity_delta: quantityDelta,
        value_delta: 0, // Would need prices to calculate
        rationale: "Position size changed since last review",
      });
    }
  }

  // Analyze current positions for new or large holdings
  for (const account of accountsWithPositions) {
    for (const position of account.positions) {
      if (position.weight_pct > 10) {
        deltas.push({
          symbol: position.symbol,
          change_type: "concentration",
          quantity_delta: position.quantity,
          value_delta: position.current_value_usd,
          rationale: `${position.position_name} represents ${position.weight_pct}% of portfolio`,
        });
      }

      if (position.unrealized_gain_loss_pct > 30 || position.unrealized_gain_loss_pct < -20) {
        deltas.push({
          symbol: position.symbol,
          change_type: "performance_outlier",
          quantity_delta: position.quantity,
          value_delta: position.current_value_usd,
          rationale: `${position.unrealized_gain_loss_pct > 0 ? "Strong" : "Weak"} performance: ${position.unrealized_gain_loss_pct}%`,
        });
      }
    }
  }

  return deltas;
}

async function scoreEngagement(
  supabase: ReturnType<typeof createClient>,
  household: HouseholdData,
  members: any[]
): Promise<{ overall: number; cohort: string; components: Record<string, number> }> {
  let score = 50; // Base score

  // Factor 1: Meeting frequency (last 90 days)
  const { data: recentMeetings } = await supabase
    .from("meetings")
    .select("id")
    .eq("household_id", household.id)
    .gte("completed_date", new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString());

  const meetingScore = Math.min(15, (recentMeetings?.length || 0) * 5);
  score += meetingScore;

  // Factor 2: Portfolio activity (position changes, etc.)
  const { data: positionChanges } = await supabase
    .from("position_history")
    .select("id")
    .gte("recorded_at", new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString());

  const activityScore = Math.min(15, (positionChanges?.length || 0) * 3);
  score += activityScore;

  // Factor 3: Attrition risk indicators
  const daysSinceReview = household.last_review_date
    ? Math.floor((Date.now() - new Date(household.last_review_date).getTime()) / (24 * 60 * 60 * 1000))
    : 365;

  const attritionDelta = daysSinceReview > 180 ? -15 : daysSinceReview > 365 ? -20 : 0;
  score += attritionDelta;

  // Factor 4: Communication sentiment (from meeting notes)
  const { data: meetingNotes } = await supabase
    .from("meeting_notes")
    .select("note_type")
    .eq("note_type", "concern");

  const concernCount = meetingNotes?.length || 0;
  const sentimentScore = concernCount > 2 ? -10 : 0;
  score += sentimentScore;

  // Ensure score stays in bounds
  score = Math.max(0, Math.min(100, score));

  // Determine cohort
  let cohort = "growth";
  if (score >= 76) cohort = "premier";
  else if (score >= 51) cohort = "core";
  else if (score < 26) cohort = "at_risk";

  return {
    overall: score,
    cohort,
    components: {
      meeting: meetingScore,
      activity: activityScore,
      attrition: attritionDelta,
      sentiment: sentimentScore,
    },
  };
}

function generateConversationStarters(
  household: HouseholdData,
  accountsWithPositions: any[],
  positionDeltas: any[],
  engagementScore: any,
  members: any[]
): string[] {
  const starters = [];

  // Portfolio-based starters
  if (positionDeltas.some((d) => d.change_type === "concentration")) {
    starters.push(
      `Review of concentrated positions - discuss risk management and diversification strategy`
    );
  }

  if (positionDeltas.some((d) => d.change_type === "performance_outlier")) {
    starters.push(`Address significant portfolio performance variations and rebalancing needs`);
  }

  // Engagement-based starters
  if (engagementScore.cohort === "at_risk") {
    starters.push(
      `Reconnect on financial goals and ensure portfolio aligns with current objectives`
    );
  }

  if (engagementScore.cohort === "premier") {
    starters.push(
      `Discuss advanced strategies: tax-loss harvesting, charitable giving, legacy planning`
    );
  }

  // Life event based
  if (members.length > 1) {
    starters.push(
      `Review beneficiary designations and account titling with ${members.length} household members`
    );
  }

  // AUM-based
  if (household.aum_usd > 5000000) {
    starters.push(
      `Consider alternative investments and institutional share class opportunities`
    );
  }

  starters.push(`Review and confirm annual financial planning priorities`);

  return starters.slice(0, 5); // Return top 5
}

function computeAssetAllocation(accountsWithPositions: any[]): Record<string, number> {
  const allocation = {
    domestic_equity: 0,
    intl_equity: 0,
    fixed_income: 0,
    commodities: 0,
    alternatives: 0,
  };

  const totalValue = accountsWithPositions.reduce(
    (sum, acc) => sum + (acc.total_value_usd || 0),
    0
  );

  for (const account of accountsWithPositions) {
    for (const position of account.positions || []) {
      const weight = (position.current_value_usd / totalValue) * 100;
      const assetClass = position.asset_class || "alternatives";
      allocation[assetClass as keyof typeof allocation] =
        (allocation[assetClass as keyof typeof allocation] || 0) + weight;
    }
  }

  return allocation;
}

function computePortfolioPerformance(accountsWithPositions: any[]): { pct: number; amount: number } {
  let totalGainLoss = 0;
  let totalValue = 0;

  for (const account of accountsWithPositions) {
    totalValue += account.total_value_usd || 0;
    for (const position of account.positions || []) {
      totalGainLoss += position.unrealized_gain_loss_usd || 0;
    }
  }

  const pct = totalValue > 0 ? (totalGainLoss / (totalValue - totalGainLoss)) * 100 : 0;

  return { pct: Math.round(pct * 100) / 100, amount: totalGainLoss };
}

function assembleBriefingContent(
  household: HouseholdData,
  members: any[],
  accountsWithPositions: any[],
  positionDeltas: any[],
  engagementScore: any,
  conversationStarters: string[]
): Record<string, any> {
  return {
    title: `Client Review Briefing: ${household.household_name}`,
    generated_at: new Date().toISOString(),
    household: {
      name: household.household_name,
      primary_contact: household.primary_contact_name,
      aum: household.aum_usd,
      members: members.map((m) => ({
        name: `${m.first_name} ${m.last_name}`,
        relationship: m.relationship,
      })),
    },
    engagement: {
      score: engagementScore.overall,
      cohort: engagementScore.cohort,
      days_since_last_review: household.last_review_date
        ? Math.floor((Date.now() - new Date(household.last_review_date).getTime()) / (24 * 60 * 60 * 1000))
        : null,
    },
    portfolio: {
      accounts: accountsWithPositions.length,
      total_value: accountsWithPositions.reduce(
        (sum, acc) => sum + (acc.total_value_usd || 0),
        0
      ),
      asset_allocation: computeAssetAllocation(accountsWithPositions),
      performance: computePortfolioPerformance(accountsWithPositions),
    },
    position_changes: positionDeltas.slice(0, 10),
    conversation_starters: conversationStarters,
  };
}

function generateBriefingMarkdown(briefingContent: Record<string, any>): string {
  return `# ${briefingContent.title}

Generated: ${new Date(briefingContent.generated_at).toLocaleDateString()}

## Household Summary
- **Name:** ${briefingContent.household.name}
- **Primary Contact:** ${briefingContent.household.primary_contact}
- **Total AUM:** $${(briefingContent.household.aum / 1000000).toFixed(2)}M
- **Members:** ${briefingContent.household.members.length}

## Engagement Metrics
- **Score:** ${briefingContent.engagement.score}/100 (${briefingContent.engagement.cohort})
- **Days Since Review:** ${briefingContent.engagement.days_since_last_review || "N/A"}

## Portfolio Overview
- **Accounts:** ${briefingContent.portfolio.accounts}
- **Total Value:** $${(briefingContent.portfolio.total_value / 1000000).toFixed(2)}M
- **YTD Performance:** ${briefingContent.portfolio.performance.pct}% ($${(briefingContent.portfolio.performance.amount / 1000).toFixed(0)}K)

## Asset Allocation
${Object.entries(briefingContent.portfolio.asset_allocation)
  .map(([asset, pct]) => `- ${asset}: ${(pct as number).toFixed(1)}%`)
  .join("\n")}

## Position Changes
${briefingContent.position_changes
  .map(
    (change: any) =>
      `- **${change.symbol}:** ${change.change_type} (Δ ${change.quantity_delta} shares / $${(change.value_delta / 1000).toFixed(0)}K)`
  )
  .join("\n")}

## Conversation Starters
${briefingContent.conversation_starters.map((starter: string) => `- ${starter}`).join("\n")}
`;
}

function generateBriefingHtml(briefingContent: Record<string, any>): string {
  return `
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }
    h1 { color: #1e3a8a; border-bottom: 2px solid #1e3a8a; }
    h2 { color: #1e40af; margin-top: 20px; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
    td, th { padding: 8px; text-align: left; border: 1px solid #ddd; }
    th { background-color: #f0f0f0; }
    .metric { display: inline-block; margin: 10px 20px 10px 0; }
    .metric-value { font-size: 1.5em; font-weight: bold; color: #1e3a8a; }
    .metric-label { font-size: 0.9em; color: #666; }
  </style>
</head>
<body>
  <h1>${briefingContent.title}</h1>
  <p><small>Generated: ${new Date(briefingContent.generated_at).toLocaleString()}</small></p>

  <h2>Household Summary</h2>
  <p><strong>Name:</strong> ${briefingContent.household.name}</p>
  <p><strong>Primary Contact:</strong> ${briefingContent.household.primary_contact}</p>
  <p><strong>Total AUM:</strong> $${(briefingContent.household.aum / 1000000).toFixed(2)}M</p>

  <h2>Engagement Metrics</h2>
  <div class="metric">
    <div class="metric-value">${briefingContent.engagement.score}</div>
    <div class="metric-label">Engagement Score (${briefingContent.engagement.cohort})</div>
  </div>

  <h2>Portfolio Overview</h2>
  <table>
    <tr><td><strong>Accounts:</strong></td><td>${briefingContent.portfolio.accounts}</td></tr>
    <tr><td><strong>Total Value:</strong></td><td>$${(briefingContent.portfolio.total_value / 1000000).toFixed(2)}M</td></tr>
    <tr><td><strong>YTD Performance:</strong></td><td>${briefingContent.portfolio.performance.pct}%</td></tr>
  </table>

  <h2>Asset Allocation</h2>
  <table>
    ${Object.entries(briefingContent.portfolio.asset_allocation)
      .map(
        ([asset, pct]) =>
          `<tr><td>${asset}</td><td>${((pct as number) || 0).toFixed(1)}%</td></tr>`
      )
      .join("")}
  </table>

  <h2>Conversation Starters</h2>
  <ul>
    ${briefingContent.conversation_starters.map((starter: string) => `<li>${starter}</li>`).join("")}
  </ul>
</body>
</html>
  `;
}

function generateRecommendedActions(
  positionDeltas: any[],
  engagementScore: any,
  household: HouseholdData
): Array<{ action: string; priority: number; estimated_time: string }> {
  const actions = [];

  if (positionDeltas.some((d) => d.change_type === "concentration")) {
    actions.push({
      action: "Review concentrated positions and discuss diversification strategy",
      priority: 1,
      estimated_time: "15 min",
    });
  }

  if (engagementScore.cohort === "at_risk") {
    actions.push({
      action: "Deep dive on financial goals and risk tolerance alignment",
      priority: 1,
      estimated_time: "20 min",
    });
  }

  if (household.aum_usd > 2000000) {
    actions.push({
      action: "Discuss tax-loss harvesting opportunities",
      priority: 2,
      estimated_time: "10 min",
    });
  }

  actions.push({
    action: "Confirm beneficiary designations and account titling",
    priority: 2,
    estimated_time: "10 min",
  });

  return actions.slice(0, 5);
}

async function notifyAdvisor(
  supabase: ReturnType<typeof createClient>,
  household: HouseholdData,
  briefing: any
): Promise<void> {
  const { data: advisor } = await supabase
    .from("advisors")
    .select("email")
    .eq("id", household.assigned_advisor_id)
    .single();

  if (advisor?.email) {
    // Queue email notification (would integrate with SendGrid/similar)
    logger.info(`Advisor notification queued`, {
      advisor_email: advisor.email,
      briefing_id: briefing.id,
    });
  }
}
