import { batchTrigger } from "@trigger.dev/sdk";
import { logger } from "@trigger.dev/sdk";
import { createClient } from "@supabase/supabase-js";

interface HouseholdRecord {
  id: string;
  household_name: string;
  aum_usd: number;
  last_review_date: string | null;
  attrition_risk: boolean;
}

interface EngagementMetrics {
  household_id: string;
  meeting_frequency_score: number;
  portfolio_activity_score: number;
  attrition_risk_delta: number;
  communication_sentiment_score: number;
  overall_score: number;
  cohort: "at_risk" | "growth" | "core" | "premier";
}

export const engagementBatchJob = batchTrigger({
  name: "engagement_batch",
  onRun: async (event, { ctx }) => {
    const supabase = createClient(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );

    logger.info("Starting batch engagement scoring job");

    try {
      // Fetch all active households
      const { data: households, error: householdsError } = await supabase
        .from("households")
        .select("id, household_name, aum_usd, last_review_date, attrition_risk");

      if (householdsError) {
        throw new Error(`Failed to fetch households: ${householdsError.message}`);
      }

      logger.info(`Processing ${households?.length || 0} households for engagement scoring`);

      const startTime = Date.now();
      const batch = households || [];
      const batchSize = 100; // Process in chunks to avoid overload
      const results: EngagementMetrics[] = [];
      let successCount = 0;
      let failureCount = 0;

      for (let i = 0; i < batch.length; i += batchSize) {
        const chunk = batch.slice(i, i + batchSize);
        logger.info(`Processing batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(batch.length / batchSize)}`);

        const chunkResults = await Promise.allSettled(
          chunk.map((household) => scoreHouseholdEngagement(supabase, household))
        );

        chunkResults.forEach((result, index) => {
          if (result.status === "fulfilled") {
            results.push(result.value);
            successCount++;
          } else {
            logger.warn(`Failed to score household ${chunk[index].id}`, {
              error: result.reason?.message || String(result.reason),
            });
            failureCount++;
          }
        });

        // Small delay between chunks to avoid rate limiting
        if (i + batchSize < batch.length) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
      }

      // Bulk upsert engagement scores
      const scoresToInsert = results.map((metric) => ({
        household_id: metric.household_id,
        score_date: new Date().toISOString().split("T")[0],
        overall_score: metric.overall_score,
        cohort: metric.cohort,
        meeting_frequency_score: metric.meeting_frequency_score,
        portfolio_activity_score: metric.portfolio_activity_score,
        attrition_risk_delta: metric.attrition_risk_delta,
        communication_sentiment_score: metric.communication_sentiment_score,
        calculation_metadata: {
          components: {
            meeting: metric.meeting_frequency_score,
            activity: metric.portfolio_activity_score,
            attrition: metric.attrition_risk_delta,
            sentiment: metric.communication_sentiment_score,
          },
          timestamp: new Date().toISOString(),
        },
      }));

      if (scoresToInsert.length > 0) {
        const { error: insertError } = await supabase
          .from("engagement_scores")
          .insert(scoresToInsert);

        if (insertError) {
          logger.warn(`Failed to insert some engagement scores`, {
            error: insertError.message,
          });
        } else {
          logger.info(`Successfully inserted ${scoresToInsert.length} engagement scores`);
        }
      }

      // Update household engagement_score and cohort fields
      const updatePromises = results.map((metric) =>
        supabase
          .from("households")
          .update({
            engagement_score: metric.overall_score,
            engagement_cohort: metric.cohort,
            attrition_risk: metric.cohort === "at_risk",
            attrition_risk_score: metric.attrition_risk_delta,
          })
          .eq("id", metric.household_id)
      );

      const updateResults = await Promise.allSettled(updatePromises);
      const updateSuccesses = updateResults.filter((r) => r.status === "fulfilled").length;

      logger.info(`Updated ${updateSuccesses} household engagement scores`);

      // Calculate cohort statistics
      const cohortStats = calculateCohortStatistics(results);
      logger.info("Cohort distribution", cohortStats);

      // Log sync completion
      const elapsed = Date.now() - startTime;
      const { error: logError } = await supabase.from("sync_logs").insert({
        organization_id: process.env.ORG_ID,
        sync_type: "engagement_batch",
        status: failureCount === 0 ? "success" : "partial",
        records_processed: batch.length,
        records_failed: failureCount,
        metadata: {
          cohort_stats: cohortStats,
          elapsed_ms: elapsed,
          avg_score: results.length > 0
            ? Math.round(results.reduce((sum, r) => sum + r.overall_score, 0) / results.length)
            : 0,
        },
      });

      if (logError) {
        logger.warn("Failed to log sync completion", { error: logError.message });
      }

      // Identify at-risk households for alerts
      const atRiskHouseholds = results.filter((r) => r.cohort === "at_risk");
      if (atRiskHouseholds.length > 0) {
        await alertOnAtRiskHouseholds(supabase, atRiskHouseholds);
      }

      logger.info("Batch engagement scoring completed", {
        total_processed: batch.length,
        successes: successCount,
        failures: failureCount,
        elapsed_ms: elapsed,
        at_risk_count: atRiskHouseholds.length,
      });

      return {
        success: true,
        processed: batch.length,
        successes: successCount,
        failures: failureCount,
        elapsed_ms: elapsed,
        at_risk_identified: atRiskHouseholds.length,
      };
    } catch (error) {
      logger.error("Engagement batch job failed", {
        error: error instanceof Error ? error.message : String(error),
      });

      // Log failure
      await supabase.from("sync_logs").insert({
        organization_id: process.env.ORG_ID,
        sync_type: "engagement_batch",
        status: "failed",
        error_message: error instanceof Error ? error.message : String(error),
        records_processed: 0,
        records_failed: 0,
      });

      throw error;
    }
  },
  concurrencyLimit: 10, // Limit concurrent executions
});

async function scoreHouseholdEngagement(
  supabase: ReturnType<typeof createClient>,
  household: HouseholdRecord
): Promise<EngagementMetrics> {
  let baseScore = 50;
  const components = {
    meeting_frequency: 0,
    portfolio_activity: 0,
    attrition_risk: 0,
    communication_sentiment: 0,
  };

  // Component 1: Meeting frequency (0-15 points)
  const { data: recentMeetings } = await supabase
    .from("meetings")
    .select("id, sentiment")
    .eq("household_id", household.id)
    .gte("completed_date", new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString());

  let meetingScore = 0;
  if ((recentMeetings?.length || 0) > 0) {
    meetingScore = Math.min(15, (recentMeetings?.length || 0) * 5);
  } else if (!household.last_review_date || Date.now() - new Date(household.last_review_date).getTime() < 180 * 24 * 60 * 60 * 1000) {
    meetingScore = 8; // Good standing
  }
  components.meeting_frequency = meetingScore;

  // Component 2: Portfolio activity (0-15 points)
  const { data: positionChanges } = await supabase
    .from("position_history")
    .select("id")
    .in("account_id", [
      ...(await supabase
        .from("accounts")
        .select("id")
        .eq("household_id", household.id)
        .then((r) => r.data?.map((a) => a.id) || []))
    ])
    .gte("recorded_at", new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString());

  const activityScore = Math.min(15, ((positionChanges?.length || 0) / 2) * 5);
  components.portfolio_activity = activityScore;

  // Component 3: Attrition risk (−20 to +10)
  const daysSinceReview = household.last_review_date
    ? Math.floor((Date.now() - new Date(household.last_review_date).getTime()) / (24 * 60 * 60 * 1000))
    : 999;

  let attritionScore = 0;
  if (daysSinceReview > 365) {
    attritionScore = -20;
  } else if (daysSinceReview > 180) {
    attritionScore = -15;
  } else if (daysSinceReview > 270) {
    attritionScore = -10;
  } else if (daysSinceReview < 90) {
    attritionScore = +10;
  } else {
    attritionScore = 0;
  }
  components.attrition_risk = attritionScore;

  // Component 4: Communication sentiment (0-10)
  const { data: concernNotes } = await supabase
    .from("meeting_notes")
    .select("id")
    .in("meeting_id", [
      ...(await supabase
        .from("meetings")
        .select("id")
        .eq("household_id", household.id)
        .then((r) => r.data?.map((m) => m.id) || []))
    ])
    .eq("note_type", "concern");

  const sentimentScore = Math.max(0, 10 - ((concernNotes?.length || 0) * 2));
  components.communication_sentiment = sentimentScore;

  // Calculate overall score
  const overallScore = Math.max(0, Math.min(100, baseScore + meetingScore + activityScore + attritionScore + sentimentScore));

  // Determine cohort
  let cohort: "at_risk" | "growth" | "core" | "premier" = "growth";
  if (overallScore >= 76) {
    cohort = "premier";
  } else if (overallScore >= 51) {
    cohort = "core";
  } else if (overallScore < 26) {
    cohort = "at_risk";
  }

  return {
    household_id: household.id,
    overall_score: overallScore,
    cohort,
    meeting_frequency_score: meetingScore,
    portfolio_activity_score: activityScore,
    attrition_risk_delta: attritionScore,
    communication_sentiment_score: sentimentScore,
  };
}

function calculateCohortStatistics(metrics: EngagementMetrics[]): Record<string, any> {
  const cohorts = { at_risk: 0, growth: 0, core: 0, premier: 0 };
  const scores = { at_risk: [], growth: [], core: [], premier: [] };

  for (const metric of metrics) {
    cohorts[metric.cohort]++;
    scores[metric.cohort].push(metric.overall_score);
  }

  return {
    at_risk: {
      count: cohorts.at_risk,
      avg_score: cohorts.at_risk > 0
        ? Math.round(scores.at_risk.reduce((a, b) => a + b, 0) / cohorts.at_risk)
        : 0,
    },
    growth: {
      count: cohorts.growth,
      avg_score: cohorts.growth > 0
        ? Math.round(scores.growth.reduce((a, b) => a + b, 0) / cohorts.growth)
        : 0,
    },
    core: {
      count: cohorts.core,
      avg_score: cohorts.core > 0
        ? Math.round(scores.core.reduce((a, b) => a + b, 0) / cohorts.core)
        : 0,
    },
    premier: {
      count: cohorts.premier,
      avg_score: cohorts.premier > 0
        ? Math.round(scores.premier.reduce((a, b) => a + b, 0) / cohorts.premier)
        : 0,
    },
  };
}

async function alertOnAtRiskHouseholds(
  supabase: ReturnType<typeof createClient>,
  atRiskMetrics: EngagementMetrics[]
): Promise<void> {
  logger.info(`Identified ${atRiskMetrics.length} at-risk households, preparing alerts`);

  // Fetch compliance officers
  const { data: complianceOfficers } = await supabase
    .from("advisors")
    .select("id, email")
    .eq("role", "compliance")
    .eq("active", true);

  if (!complianceOfficers?.length) {
    logger.warn("No compliance officers found for at-risk alerts");
    return;
  }

  // Would integrate with email system here to send alert emails
  logger.info(`Would send at-risk alerts to ${complianceOfficers.length} compliance officers`);
}
