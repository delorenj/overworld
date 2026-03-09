/**
 * Onboarding Empty State Component
 * 
 * Interactive 3-step tour for first-time users with no maps.
 * Guides users through: Upload → Generate → Download
 * 
 * From UX Audit P1 Item #4:
 * - Replace "No maps yet" with actionable onboarding
 * - Impact: +30% new user activation
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Upload, 
  Sparkles, 
  ArrowRight, 
  FileText,
  Wand2,
  ImageDown
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';

interface OnboardingStep {
  number: number;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
}

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    number: 1,
    title: 'Upload Your Document',
    description: 'Start by uploading a markdown or PDF file containing your project structure, roadmap, or documentation.',
    icon: FileText,
    action: {
      label: 'Upload Document',
      href: '/dashboard/upload',
    },
  },
  {
    number: 2,
    title: 'Generate Your Map',
    description: 'Our AI will analyze your document and create a beautiful visual overworld map with regions, milestones, and connections.',
    icon: Wand2,
  },
  {
    number: 3,
    title: 'Download & Share',
    description: 'Export your map as PNG or SVG. Share it with your team or embed it in your documentation.',
    icon: ImageDown,
  },
];

export function OnboardingEmptyState() {
  const [hoveredStep, setHoveredStep] = useState<number | null>(null);

  return (
    <div className="max-w-5xl mx-auto py-12 px-4">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 mb-6 animate-pulse">
          <Sparkles className="h-10 w-10 text-white" />
        </div>
        <h2 className="text-3xl font-bold text-foreground mb-3">
          Welcome to Overworld
        </h2>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Transform your documents into interactive roadmap maps in 3 simple steps
        </p>
      </div>

      {/* 3-Step Visual Guide */}
      <div className="grid gap-6 md:grid-cols-3 mb-8">
        {ONBOARDING_STEPS.map((step, index) => {
          const Icon = step.icon;
          const isHovered = hoveredStep === step.number;
          const isFirst = index === 0;

          return (
            <div key={step.number} className="relative">
              {/* Connector Arrow (between cards) */}
              {index < ONBOARDING_STEPS.length - 1 && (
                <div className="hidden md:flex absolute top-24 -right-8 z-10 items-center justify-center w-16">
                  <ArrowRight className="h-6 w-6 text-muted-foreground" />
                </div>
              )}

              <Card
                className={cn(
                  'relative overflow-hidden transition-all duration-300 h-full',
                  isHovered && 'shadow-xl scale-105',
                  isFirst && 'ring-2 ring-primary'
                )}
                onMouseEnter={() => setHoveredStep(step.number)}
                onMouseLeave={() => setHoveredStep(null)}
              >
                <CardContent className="p-6">
                  {/* Step Number Badge */}
                  <div className="flex items-center justify-between mb-4">
                    <Badge 
                      variant={isFirst ? 'default' : 'secondary'}
                      className="text-lg px-3 py-1"
                    >
                      Step {step.number}
                    </Badge>
                    {isFirst && (
                      <Badge variant="outline" className="animate-pulse">
                        Start Here
                      </Badge>
                    )}
                  </div>

                  {/* Icon */}
                  <div className={cn(
                    'inline-flex items-center justify-center w-14 h-14 rounded-xl mb-4 transition-colors',
                    isFirst 
                      ? 'bg-primary/10 text-primary' 
                      : 'bg-muted text-muted-foreground'
                  )}>
                    <Icon className="h-7 w-7" />
                  </div>

                  {/* Content */}
                  <h3 className="text-xl font-semibold text-foreground mb-2">
                    {step.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    {step.description}
                  </p>

                  {/* Action Button (only for step 1) */}
                  {step.action && (
                    <Button 
                      asChild={!!step.action.href}
                      className="w-full mt-2"
                      size="lg"
                    >
                      {step.action.href ? (
                        <Link to={step.action.href}>
                          <Upload className="mr-2 h-4 w-4" />
                          {step.action.label}
                        </Link>
                      ) : (
                        <button onClick={step.action.onClick}>
                          {step.action.label}
                        </button>
                      )}
                    </Button>
                  )}
                </CardContent>
              </Card>
            </div>
          );
        })}
      </div>

      {/* Quick Stats / Trust Signals */}
      <div className="mt-12 pt-8 border-t border-border">
        <div className="grid grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold text-foreground mb-1">
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                2 min
              </span>
            </div>
            <p className="text-sm text-muted-foreground">Average generation time</p>
          </div>
          <div>
            <div className="text-3xl font-bold text-foreground mb-1">
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                100%
              </span>
            </div>
            <p className="text-sm text-muted-foreground">Free to start</p>
          </div>
          <div>
            <div className="text-3xl font-bold text-foreground mb-1">
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                PNG/SVG
              </span>
            </div>
            <p className="text-sm text-muted-foreground">Export formats</p>
          </div>
        </div>
      </div>

      {/* Example CTA */}
      <div className="mt-8 text-center">
        <p className="text-sm text-muted-foreground mb-4">
          Already have a document ready?
        </p>
        <Button asChild size="lg" variant="outline">
          <Link to="/dashboard/upload">
            <Upload className="mr-2 h-4 w-4" />
            Get Started Now
          </Link>
        </Button>
      </div>
    </div>
  );
}
