import React from 'react';
import {
  Body,
  Button,
  Container,
  Head,
  Hr,
  Html,
  Img,
  Link,
  Preview,
  Row,
  Section,
  Text,
} from '@react-email/components';

interface UpcomingReview {
  household_name: string;
  review_date: string;
  briefing_status: 'ready' | 'generating' | 'pending';
  briefing_link: string;
}

interface ReviewReminderProps {
  advisor_name: string;
  review_count: number;
  upcoming_reviews: UpcomingReview[];
  app_base_url: string;
  timezone: string;
}

const baseUrl = process.env.REACT_EMAIL_BASE_URL || '';

export const ReviewReminder = ({
  advisor_name,
  review_count,
  upcoming_reviews,
  app_base_url,
  timezone,
}: ReviewReminderProps) => {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: timezone,
    };
    return date.toLocaleDateString('en-US', options);
  };

  return (
    <Html>
      <Head />
      <Preview>
        {review_count} client review{review_count !== 1 ? 's' : ''} scheduled this week
      </Preview>
      <Body style={main}>
        <Container style={container}>
          {/* Header */}
          <Section style={header}>
            <Text style={headerTitle}>Weekly Review Reminder</Text>
            <Text style={headerSubtitle}>
              {review_count} client{review_count !== 1 ? 's' : ''} scheduled this week
            </Text>
          </Section>

          {/* Greeting */}
          <Section style={content}>
            <Text style={greeting}>Hi {advisor_name},</Text>
            <Text style={body}>
              You have <strong>{review_count}</strong> client review{review_count !== 1 ? 's' : ''} scheduled for this week.
              Your briefing materials are below. Take a moment to review them before your meetings.
            </Text>
          </Section>

          {/* Reviews List */}
          <Section style={reviewsSection}>
            {upcoming_reviews.map((review, index) => (
              <div key={index}>
                <Row style={reviewRow}>
                  <div style={reviewCard}>
                    <Text style={reviewHousehold}>{review.household_name}</Text>
                    <Text style={reviewDate}>
                      📅 {formatDate(review.review_date)}
                    </Text>

                    {/* Status Badge */}
                    <Row style={statusRow}>
                      <div style={getStatusBadge(review.briefing_status)}>
                        <Text style={statusText}>
                          {review.briefing_status === 'ready' && '✓ Briefing Ready'}
                          {review.briefing_status === 'generating' && '⏳ Generating...'}
                          {review.briefing_status === 'pending' && '⏱ Pending'}
                        </Text>
                      </div>
                    </Row>

                    {/* View Briefing Button */}
                    {review.briefing_status === 'ready' && (
                      <Button
                        pX={20}
                        pY={10}
                        style={button}
                        href={review.briefing_link}
                      >
                        View Briefing
                      </Button>
                    )}

                    {review.briefing_status === 'generating' && (
                      <Text style={generatingText}>
                        Briefing will be ready shortly. Check back in a few moments.
                      </Text>
                    )}
                  </div>
                </Row>
                {index < upcoming_reviews.length - 1 && (
                  <Hr style={divider} />
                )}
              </div>
            ))}
          </Section>

          {/* CTA Section */}
          <Section style={ctaSection}>
            <Button
              pX={30}
              pY={12}
              style={primaryButton}
              href={`${app_base_url}/dashboard?tab=upcoming-reviews`}
            >
              View All Reviews
            </Button>
          </Section>

          {/* Tips Section */}
          <Section style={tipsSection}>
            <Text style={tipsTitle}>💡 Review Tips</Text>
            <ul style={tipsList}>
              <li style={tipsItem}>
                <Text>
                  <strong>Start Early:</strong> Review the briefing at least 30 minutes before the meeting
                </Text>
              </Text>
              <li style={tipsItem}>
                <Text>
                  <strong>Check Changes:</strong> Pay special attention to position changes and new holdings
                </Text>
              </li>
              <li style={tipsItem}>
                <Text>
                  <strong>Prepare Questions:</strong> Use conversation starters to engage meaningfully
                </Text>
              </li>
            </ul>
          </Section>

          {/* Footer */}
          <Hr style={footerDivider} />
          <Section style={footer}>
            <Text style={footerText}>
              Questions about a briefing?{' '}
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

export default ReviewReminder;

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

const header = {
  backgroundColor: '#1e3a8a',
  padding: '32px 20px',
  textAlign: 'center' as const,
};

const headerTitle = {
  color: '#ffffff',
  fontSize: '28px',
  fontWeight: 'bold',
  margin: '0 0 8px 0',
  padding: '0',
};

const headerSubtitle = {
  color: '#93c5fd',
  fontSize: '16px',
  margin: '0',
  padding: '0',
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

const reviewsSection = {
  padding: '32px 20px',
  backgroundColor: '#f9fafb',
};

const reviewRow = {
  margin: '0 0 16px 0',
};

const reviewCard = {
  backgroundColor: '#ffffff',
  border: '1px solid #e5e7eb',
  borderRadius: '8px',
  padding: '20px',
  width: '100%',
};

const reviewHousehold = {
  fontSize: '16px',
  fontWeight: '600',
  color: '#1f2937',
  margin: '0 0 8px 0',
  padding: '0',
};

const reviewDate = {
  fontSize: '14px',
  color: '#6b7280',
  margin: '0 0 12px 0',
  padding: '0',
};

const statusRow = {
  margin: '12px 0',
};

const getStatusBadge = (status: string) => {
  const baseStyles = {
    display: 'inline-block' as const,
    padding: '6px 12px',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: '500' as const,
    margin: '8px 0',
  };

  switch (status) {
    case 'ready':
      return {
        ...baseStyles,
        backgroundColor: '#dcfce7',
        border: '1px solid #86efac',
      };
    case 'generating':
      return {
        ...baseStyles,
        backgroundColor: '#fef3c7',
        border: '1px solid #fde047',
      };
    case 'pending':
      return {
        ...baseStyles,
        backgroundColor: '#f3f4f6',
        border: '1px solid #d1d5db',
      };
    default:
      return baseStyles;
  }
};

const statusText = {
  margin: '0',
  padding: '0',
  fontSize: '12px',
  fontWeight: '500',
};

const button = {
  backgroundColor: '#1e3a8a',
  color: '#ffffff',
  fontSize: '14px',
  fontWeight: '600',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  marginTop: '12px',
  padding: '10px 20px',
  textDecoration: 'none',
  display: 'inline-block',
  textAlign: 'center' as const,
};

const generatingText = {
  fontSize: '13px',
  color: '#6b7280',
  fontStyle: 'italic',
  margin: '12px 0 0 0',
  padding: '0',
};

const divider = {
  borderColor: '#e5e7eb',
  margin: '24px 0',
};

const ctaSection = {
  padding: '32px 20px',
  textAlign: 'center' as const,
};

const primaryButton = {
  backgroundColor: '#1e3a8a',
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

const tipsSection = {
  padding: '24px 20px',
  backgroundColor: '#f0f9ff',
  border: '1px solid #bfdbfe',
  borderRadius: '8px',
  margin: '0 20px 32px 20px',
};

const tipsTitle = {
  fontSize: '14px',
  fontWeight: '600',
  color: '#1e40af',
  margin: '0 0 12px 0',
  padding: '0',
};

const tipsList = {
  margin: '0',
  padding: '0 0 0 20px',
};

const tipsItem = {
  margin: '8px 0',
  color: '#374151',
  fontSize: '13px',
  lineHeight: '20px',
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
