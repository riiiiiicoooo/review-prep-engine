import React from 'react';
import {
  Body,
  Button,
  Container,
  Head,
  Hr,
  Html,
  Link,
  Preview,
  Row,
  Section,
  Text,
} from '@react-email/components';

interface AttritionHousehold {
  household_id: string;
  household_name: string;
  primary_contact_name: string;
  aum_usd: number;
  engagement_score: number;
  days_since_review: number;
  attrition_risk_factors: string[];
  recommended_actions: Array<{
    action: string;
    priority: number;
  }>;
}

interface AttritionAlertProps {
  compliance_officer_name: string;
  at_risk_households: AttritionHousehold[];
  app_base_url: string;
}

const baseUrl = process.env.REACT_EMAIL_BASE_URL || '';

export const AttritionAlert = ({
  compliance_officer_name,
  at_risk_households,
  app_base_url,
}: AttritionAlertProps) => {
  const totalAUM = at_risk_households.reduce((sum, h) => sum + h.aum_usd, 0);
  const criticalCount = at_risk_households.filter((h) => h.engagement_score < 25).length;

  return (
    <Html>
      <Head />
      <Preview>
        Alert: {at_risk_households.length} at-risk client(s) identified
      </Preview>
      <Body style={main}>
        <Container style={container}>
          {/* Alert Header */}
          <Section style={alertHeader}>
            <Text style={alertTitle}>⚠️ Client Attrition Risk Alert</Text>
            <Text style={alertSubtitle}>
              {at_risk_households.length} household(s) flagged for engagement review
            </Text>
          </Section>

          {/* Quick Stats */}
          <Section style={statsSection}>
            <Row style={statsRow}>
              <div style={statBox}>
                <Text style={statNumber}>{at_risk_households.length}</Text>
                <Text style={statLabel}>At-Risk Households</Text>
              </div>
              <div style={statDivider} />
              <div style={statBox}>
                <Text style={statNumber}>${(totalAUM / 1000000).toFixed(1)}M</Text>
                <Text style={statLabel}>Total AUM at Risk</Text>
              </div>
              <div style={statDivider} />
              <div style={statBox}>
                <Text style={statNumber}>{criticalCount}</Text>
                <Text style={statLabel}>Critical Status</Text>
              </div>
            </Row>
          </Section>

          {/* Message */}
          <Section style={content}>
            <Text style={greeting}>Hi {compliance_officer_name},</Text>
            <Text style={body}>
              The engagement scoring system has identified {at_risk_households.length} households
              with declining engagement metrics. These require immediate attention from their assigned advisors.
            </Text>
          </Section>

          {/* Households List */}
          {at_risk_households.map((household, index) => (
            <Section key={household.household_id} style={householdSection}>
              <div style={householdCard}>
                {/* Household Header */}
                <Row style={householdHeader}>
                  <div>
                    <Text style={householdName}>{household.household_name}</Text>
                    <Text style={householdContact}>
                      Primary Contact: {household.primary_contact_name}
                    </Text>
                  </div>
                  <div style={riskBadge(getRiskLevel(household.engagement_score))}>
                    <Text style={riskText}>
                      {getRiskLabel(household.engagement_score)}
                    </Text>
                  </div>
                </Row>

                {/* Metrics */}
                <Row style={metricsRow}>
                  <div style={metricColumn}>
                    <Text style={metricLabel}>Engagement Score</Text>
                    <div style={scoreBar}>
                      <div
                        style={scoreBarFill(household.engagement_score)}
                      />
                    </div>
                    <Text style={metricValue}>{household.engagement_score}/100</Text>
                  </div>
                </Row>

                <Row style={metricsRow}>
                  <div style={metricColumn}>
                    <Text style={metricLabel}>Days Since Review</Text>
                    <Text style={metricValue}>{household.days_since_review} days</Text>
                    {household.days_since_review > 365 && (
                      <Text style={warningText}>Over 1 year since last review</Text>
                    )}
                  </div>
                  <div style={metricSpacer} />
                  <div style={metricColumn}>
                    <Text style={metricLabel}>AUM</Text>
                    <Text style={metricValue}>
                      ${(household.aum_usd / 1000000).toFixed(2)}M
                    </Text>
                  </div>
                </Row>

                {/* Risk Factors */}
                {household.attrition_risk_factors.length > 0 && (
                  <>
                    <Hr style={householdDivider} />
                    <div>
                      <Text style={sectionTitle}>Risk Factors</Text>
                      <ul style={factorsList}>
                        {household.attrition_risk_factors.map((factor, i) => (
                          <li key={i} style={factorItem}>
                            <Text>{factor}</Text>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </>
                )}

                {/* Recommended Actions */}
                {household.recommended_actions.length > 0 && (
                  <>
                    <Hr style={householdDivider} />
                    <div>
                      <Text style={sectionTitle}>Recommended Actions</Text>
                      {household.recommended_actions.map((action, i) => (
                        <Row key={i} style={actionRow}>
                          <div
                            style={getPriorityBadge(action.priority)}
                          >
                            <Text style={priorityText}>
                              {action.priority === 1 ? '🔴' : '🟡'} {action.action}
                            </Text>
                          </div>
                        </Row>
                      ))}
                    </div>
                  </>
                )}

                {/* CTA */}
                <Row style={householdCTA}>
                  <Button
                    pX={20}
                    pY={10}
                    style={secondaryButton}
                    href={`${app_base_url}/households/${household.household_id}`}
                  >
                    View Full Profile
                  </Button>
                </Row>
              </div>
              {index < at_risk_households.length - 1 && (
                <Hr style={householdDivider} />
              )}
            </Section>
          ))}

          {/* Guidance Section */}
          <Section style={guidanceSection}>
            <Text style={guidanceTitle}>📋 Recommended Advisor Actions</Text>
            <ol style={guidanceList}>
              <li style={guidanceItem}>
                <Text>
                  <strong>Schedule a Call:</strong> Reach out to discuss any life changes or concerns
                </Text>
              </li>
              <li style={guidanceItem}>
                <Text>
                  <strong>Review Goals:</strong> Ensure portfolio still aligns with objectives
                </Text>
              </li>
              <li style={guidanceItem}>
                <Text>
                  <strong>Demonstrate Value:</strong> Share recent tax-loss harvesting, rebalancing, or performance highlights
                </Text>
              </li>
              <li style={guidanceItem}>
                <Text>
                  <strong>Document Interaction:</strong> Log the conversation in CRM for audit trail
                </Text>
              </li>
            </ol>
          </Section>

          {/* CTA Section */}
          <Section style={ctaSection}>
            <Button
              pX={30}
              pY={12}
              style={primaryButton}
              href={`${app_base_url}/dashboard?tab=at-risk`}
            >
              View All At-Risk Households
            </Button>
          </Section>

          {/* Footer */}
          <Hr style={footerDivider} />
          <Section style={footer}>
            <Text style={footerText}>
              This alert was generated by the Review Prep Engine engagement scoring system.
            </Text>
            <Text style={footerText}>
              Questions?{' '}
              <Link href={`${app_base_url}/support`} style={link}>
                Contact support
              </Link>
            </Text>
            <Text style={footerText}>
              {new Date().getFullYear()} Review Prep Engine. All rights reserved.
            </Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
};

export default AttritionAlert;

/* ============================================================================
   HELPER FUNCTIONS
   ============================================================================ */

function getRiskLevel(score: number): 'critical' | 'high' | 'medium' {
  if (score < 25) return 'critical';
  if (score < 40) return 'high';
  return 'medium';
}

function getRiskLabel(score: number): string {
  if (score < 25) return 'CRITICAL';
  if (score < 40) return 'HIGH';
  return 'MEDIUM';
}

function getPriorityBadge(priority: number) {
  const baseStyles = {
    padding: '8px 12px',
    borderRadius: '4px',
    marginBottom: '8px',
    display: 'block' as const,
  };

  if (priority === 1) {
    return {
      ...baseStyles,
      backgroundColor: '#fee2e2',
      borderLeft: '4px solid #dc2626',
    };
  } else {
    return {
      ...baseStyles,
      backgroundColor: '#fef3c7',
      borderLeft: '4px solid #f59e0b',
    };
  }
}

/* ============================================================================
   STYLES
   ============================================================================ */

const main = {
  backgroundColor: '#f9fafb',
  fontFamily:
    '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Ubuntu,sans-serif',
};

const container = {
  backgroundColor: '#ffffff',
  margin: '0 auto',
  padding: '20px 0',
  marginBottom: '64px',
};

const alertHeader = {
  backgroundColor: '#7f1d1d',
  padding: '32px 20px',
  textAlign: 'center' as const,
};

const alertTitle = {
  color: '#ffffff',
  fontSize: '28px',
  fontWeight: 'bold',
  margin: '0 0 8px 0',
  padding: '0',
};

const alertSubtitle = {
  color: '#fecaca',
  fontSize: '16px',
  margin: '0',
  padding: '0',
};

const statsSection = {
  padding: '32px 20px',
  backgroundColor: '#f3f4f6',
};

const statsRow = {
  display: 'flex',
  justifyContent: 'space-around',
  textAlign: 'center' as const,
};

const statBox = {
  flex: 1,
};

const statNumber = {
  fontSize: '32px',
  fontWeight: 'bold',
  color: '#1f2937',
  margin: '0 0 4px 0',
};

const statLabel = {
  fontSize: '12px',
  color: '#6b7280',
  margin: '0',
  padding: '0',
};

const statDivider = {
  width: '1px',
  backgroundColor: '#e5e7eb',
  margin: '0 16px',
};

const content = {
  padding: '32px 20px',
};

const greeting = {
  fontSize: '16px',
  fontWeight: 'bold',
  color: '#1f2937',
  margin: '0 0 16px 0',
};

const body = {
  color: '#4b5563',
  fontSize: '15px',
  lineHeight: '24px',
  margin: '16px 0',
};

const householdSection = {
  padding: '0 20px 24px 20px',
};

const householdCard = {
  border: '1px solid #e5e7eb',
  borderRadius: '8px',
  padding: '20px',
  backgroundColor: '#ffffff',
};

const householdHeader = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  marginBottom: '16px',
};

const householdName = {
  fontSize: '16px',
  fontWeight: '600',
  color: '#1f2937',
  margin: '0 0 4px 0',
};

const householdContact = {
  fontSize: '13px',
  color: '#6b7280',
  margin: '0',
};

const riskBadge = (level: string) => {
  const baseStyles = {
    padding: '8px 16px',
    borderRadius: '6px',
    textAlign: 'center' as const,
    whiteSpace: 'nowrap' as const,
  };

  if (level === 'critical') {
    return {
      ...baseStyles,
      backgroundColor: '#fecaca',
      border: '1px solid #dc2626',
    };
  } else if (level === 'high') {
    return {
      ...baseStyles,
      backgroundColor: '#fed7aa',
      border: '1px solid #f97316',
    };
  } else {
    return {
      ...baseStyles,
      backgroundColor: '#fef3c7',
      border: '1px solid #f59e0b',
    };
  }
};

const riskText = {
  fontSize: '12px',
  fontWeight: '600',
  margin: '0',
  color: '#1f2937',
};

const metricsRow = {
  display: 'flex',
  gap: '24px',
  margin: '16px 0',
};

const metricColumn = {
  flex: 1,
};

const metricLabel = {
  fontSize: '12px',
  fontWeight: '600',
  color: '#6b7280',
  margin: '0 0 8px 0',
  textTransform: 'uppercase' as const,
};

const metricValue = {
  fontSize: '18px',
  fontWeight: 'bold',
  color: '#1f2937',
  margin: '0',
};

const metricSpacer = {
  width: '1px',
  backgroundColor: '#e5e7eb',
};

const scoreBar = {
  width: '100%',
  height: '8px',
  backgroundColor: '#e5e7eb',
  borderRadius: '4px',
  overflow: 'hidden' as const,
  margin: '8px 0',
};

const scoreBarFill = (score: number) => {
  let color = '#dc2626'; // Red for low scores
  if (score >= 40) color = '#f59e0b'; // Orange
  if (score >= 60) color = '#16a34a'; // Green

  return {
    width: `${score}%`,
    height: '100%',
    backgroundColor: color,
    transition: 'width 0.3s ease',
  };
};

const warningText = {
  fontSize: '12px',
  color: '#dc2626',
  fontWeight: '500',
  margin: '4px 0 0 0',
};

const householdDivider = {
  borderColor: '#e5e7eb',
  margin: '16px 0',
};

const sectionTitle = {
  fontSize: '13px',
  fontWeight: '600',
  color: '#1f2937',
  margin: '0 0 12px 0',
  textTransform: 'uppercase' as const,
};

const factorsList = {
  margin: '0',
  padding: '0 0 0 20px',
};

const factorItem = {
  margin: '6px 0',
  color: '#6b7280',
  fontSize: '13px',
};

const actionRow = {
  margin: '8px 0',
};

const priorityText = {
  fontSize: '13px',
  color: '#1f2937',
  margin: '0',
  padding: '0',
};

const householdCTA = {
  marginTop: '16px',
};

const secondaryButton = {
  backgroundColor: '#1e3a8a',
  color: '#ffffff',
  fontSize: '14px',
  fontWeight: '600',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  padding: '10px 20px',
  textDecoration: 'none',
  display: 'inline-block',
  textAlign: 'center' as const,
};

const guidanceSection = {
  padding: '24px 20px',
  backgroundColor: '#f0f9ff',
  border: '1px solid #bfdbfe',
  borderRadius: '8px',
  margin: '0 20px 32px 20px',
};

const guidanceTitle = {
  fontSize: '14px',
  fontWeight: '600',
  color: '#1e40af',
  margin: '0 0 12px 0',
  padding: '0',
};

const guidanceList = {
  margin: '0',
  padding: '0 0 0 20px',
};

const guidanceItem = {
  margin: '10px 0',
  color: '#374151',
  fontSize: '13px',
  lineHeight: '20px',
};

const ctaSection = {
  padding: '32px 20px',
  textAlign: 'center' as const,
};

const primaryButton = {
  backgroundColor: '#7f1d1d',
  color: '#ffffff',
  fontSize: '16px',
  fontWeight: '600',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  padding: '12px 30px',
  textDecoration: 'none',
  display: 'inline-block',
  textAlign: 'center' as const,
};

const footer = {
  padding: '32px 20px',
  textAlign: 'center' as const,
};

const footerDivider = {
  borderColor: '#e5e7eb',
  margin: '0',
};

const footerText = {
  color: '#6b7280',
  fontSize: '12px',
  lineHeight: '16px',
  margin: '0 0 8px 0',
};

const link = {
  color: '#1e3a8a',
  textDecoration: 'underline',
};
