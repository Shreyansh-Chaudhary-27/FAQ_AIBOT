#!/usr/bin/env python3
"""
Load testing script for Django FAQ/RAG application.
Tests performance under concurrent user load and verifies embedding system reliability.
"""

import os
import sys
import time
import json
import threading
import statistics
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

@dataclass
class LoadTestResult:
    """Result of a single load test request."""
    endpoint: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error_message: Optional[str] = None
    response_size: int = 0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    base_url: str = "http://localhost:8000"
    concurrent_users: int = 10
    requests_per_user: int = 20
    ramp_up_time: int = 30  # seconds
    test_duration: int = 300  # seconds
    timeout: int = 30
    
    # Test endpoints
    endpoints: List[Dict] = None
    
    def __post_init__(self):
        if self.endpoints is None:
            self.endpoints = [
                {"path": "/", "method": "GET", "weight": 20},
                {"path": "/health/", "method": "GET", "weight": 10},
                {"path": "/health/embedding/", "method": "GET", "weight": 5},
                {"path": "/api/rag/query/", "method": "POST", "weight": 30, 
                 "data": {"query": "What are your business hours?"}},
                {"path": "/api/rag/query/", "method": "POST", "weight": 25,
                 "data": {"query": "How do I contact support?"}},
                {"path": "/api/rag/query/", "method": "POST", "weight": 10,
                 "data": {"query": "What services do you offer?"}},
            ]

class LoadTester:
    """Load testing framework for the FAQ/RAG application."""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[LoadTestResult] = []
        self.start_time = None
        self.end_time = None
        self.active_users = 0
        self.lock = threading.Lock()
        
        # Test queries for embedding system
        self.test_queries = [
            "What are your business hours?",
            "How do I contact support?",
            "What services do you offer?",
            "How do I reset my password?",
            "What is your refund policy?",
            "How do I create an account?",
            "What payment methods do you accept?",
            "How do I cancel my subscription?",
            "Where is your office located?",
            "Do you offer technical support?",
            "What are your pricing plans?",
            "How do I update my profile?",
            "Can I get a demo?",
            "What integrations do you support?",
            "How secure is my data?",
        ]
    
    def make_request(self, endpoint: Dict, session_id: str) -> LoadTestResult:
        """Make a single HTTP request and measure performance."""
        import requests
        
        start_time = time.time()
        
        try:
            url = f"{self.config.base_url}{endpoint['path']}"
            method = endpoint['method'].upper()
            
            # Prepare request data
            kwargs = {
                'timeout': self.config.timeout,
                'headers': {'User-Agent': f'LoadTester-Session-{session_id}'}
            }
            
            if method == 'POST' and 'data' in endpoint:
                kwargs['json'] = endpoint['data']
                kwargs['headers']['Content-Type'] = 'application/json'
            
            # Make request
            if method == 'GET':
                response = requests.get(url, **kwargs)
            elif method == 'POST':
                response = requests.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Determine success
            success = 200 <= response.status_code < 400
            
            # For RAG queries, check if we got a meaningful response
            if endpoint['path'] == '/api/rag/query/' and success:
                try:
                    response_data = response.json()
                    answer = response_data.get('answer', '')
                    if 'I don\'t know' in answer or len(answer.strip()) < 10:
                        success = False
                        error_message = "RAG system returned 'I don't know' or empty response"
                    else:
                        error_message = None
                except:
                    success = False
                    error_message = "Invalid JSON response from RAG endpoint"
            else:
                error_message = None if success else f"HTTP {response.status_code}"
            
            return LoadTestResult(
                endpoint=endpoint['path'],
                method=method,
                status_code=response.status_code,
                response_time=response_time,
                success=success,
                error_message=error_message,
                response_size=len(response.content) if hasattr(response, 'content') else 0
            )
            
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            
            return LoadTestResult(
                endpoint=endpoint['path'],
                method=endpoint['method'].upper(),
                status_code=0,
                response_time=response_time,
                success=False,
                error_message=str(e)
            )
    
    def user_session(self, user_id: int) -> List[LoadTestResult]:
        """Simulate a single user session with multiple requests."""
        session_results = []
        
        # Ramp up delay
        ramp_delay = (self.config.ramp_up_time / self.config.concurrent_users) * user_id
        time.sleep(ramp_delay)
        
        with self.lock:
            self.active_users += 1
            print(f"User {user_id} started (Active users: {self.active_users})")
        
        try:
            # Calculate weighted endpoint selection
            total_weight = sum(ep['weight'] for ep in self.config.endpoints)
            
            for request_num in range(self.config.requests_per_user):
                # Select endpoint based on weights
                import random
                rand_val = random.randint(1, total_weight)
                cumulative_weight = 0
                selected_endpoint = None
                
                for endpoint in self.config.endpoints:
                    cumulative_weight += endpoint['weight']
                    if rand_val <= cumulative_weight:
                        selected_endpoint = endpoint
                        break
                
                if selected_endpoint is None:
                    selected_endpoint = self.config.endpoints[0]
                
                # For RAG queries, use random test query
                if selected_endpoint['path'] == '/api/rag/query/':
                    query = random.choice(self.test_queries)
                    selected_endpoint = selected_endpoint.copy()
                    selected_endpoint['data'] = {"query": query}
                
                # Make request
                result = self.make_request(selected_endpoint, f"user-{user_id}")
                session_results.append(result)
                
                # Add some delay between requests (simulate user think time)
                time.sleep(random.uniform(0.5, 2.0))
                
                # Check if test duration exceeded
                if self.start_time and (time.time() - self.start_time) > self.config.test_duration:
                    break
        
        finally:
            with self.lock:
                self.active_users -= 1
                print(f"User {user_id} finished (Active users: {self.active_users})")
        
        return session_results
    
    def run_load_test(self) -> Dict:
        """Run the complete load test."""
        print(f"Starting load test with {self.config.concurrent_users} concurrent users")
        print(f"Each user will make {self.config.requests_per_user} requests")
        print(f"Ramp-up time: {self.config.ramp_up_time}s, Max duration: {self.config.test_duration}s")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # Run concurrent user sessions
        with ThreadPoolExecutor(max_workers=self.config.concurrent_users) as executor:
            futures = [
                executor.submit(self.user_session, user_id)
                for user_id in range(self.config.concurrent_users)
            ]
            
            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    session_results = future.result()
                    with self.lock:
                        self.results.extend(session_results)
                except Exception as e:
                    print(f"User session failed: {e}")
        
        self.end_time = time.time()
        
        # Generate and return report
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate comprehensive load test report."""
        if not self.results:
            return {"error": "No results to analyze"}
        
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests
        
        # Response time statistics
        response_times = [r.response_time for r in self.results]
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        p95_response_time = sorted(response_times)[int(0.95 * len(response_times))]
        p99_response_time = sorted(response_times)[int(0.99 * len(response_times))]
        
        # Throughput calculation
        test_duration = self.end_time - self.start_time
        requests_per_second = total_requests / test_duration
        
        # Error analysis
        error_counts = {}
        for result in self.results:
            if not result.success and result.error_message:
                error_counts[result.error_message] = error_counts.get(result.error_message, 0) + 1
        
        # Endpoint-specific analysis
        endpoint_stats = {}
        for result in self.results:
            key = f"{result.method} {result.endpoint}"
            if key not in endpoint_stats:
                endpoint_stats[key] = {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'response_times': []
                }
            
            endpoint_stats[key]['total'] += 1
            endpoint_stats[key]['response_times'].append(result.response_time)
            
            if result.success:
                endpoint_stats[key]['successful'] += 1
            else:
                endpoint_stats[key]['failed'] += 1
        
        # Calculate endpoint statistics
        for key, stats in endpoint_stats.items():
            stats['success_rate'] = (stats['successful'] / stats['total']) * 100
            stats['avg_response_time'] = statistics.mean(stats['response_times'])
            stats['p95_response_time'] = sorted(stats['response_times'])[int(0.95 * len(stats['response_times']))]
        
        # RAG system specific analysis
        rag_results = [r for r in self.results if r.endpoint == '/api/rag/query/']
        rag_analysis = {
            'total_queries': len(rag_results),
            'successful_queries': sum(1 for r in rag_results if r.success),
            'failed_queries': sum(1 for r in rag_results if not r.success),
            'avg_response_time': statistics.mean([r.response_time for r in rag_results]) if rag_results else 0,
            'success_rate': (sum(1 for r in rag_results if r.success) / len(rag_results) * 100) if rag_results else 0
        }
        
        report = {
            'test_config': asdict(self.config),
            'test_summary': {
                'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
                'end_time': datetime.fromtimestamp(self.end_time).isoformat(),
                'duration_seconds': test_duration,
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'success_rate_percent': (successful_requests / total_requests) * 100,
                'requests_per_second': requests_per_second
            },
            'performance_metrics': {
                'avg_response_time': avg_response_time,
                'median_response_time': median_response_time,
                'p95_response_time': p95_response_time,
                'p99_response_time': p99_response_time,
                'min_response_time': min(response_times),
                'max_response_time': max(response_times)
            },
            'error_analysis': error_counts,
            'endpoint_statistics': endpoint_stats,
            'rag_system_analysis': rag_analysis,
            'recommendations': self.generate_recommendations(endpoint_stats, rag_analysis)
        }
        
        return report
    
    def generate_recommendations(self, endpoint_stats: Dict, rag_analysis: Dict) -> List[str]:
        """Generate performance recommendations based on test results."""
        recommendations = []
        
        # Check overall performance
        for endpoint, stats in endpoint_stats.items():
            if stats['success_rate'] < 95:
                recommendations.append(f"Low success rate for {endpoint}: {stats['success_rate']:.1f}%")
            
            if stats['avg_response_time'] > 5.0:
                recommendations.append(f"High response time for {endpoint}: {stats['avg_response_time']:.2f}s")
            
            if stats['p95_response_time'] > 10.0:
                recommendations.append(f"High P95 response time for {endpoint}: {stats['p95_response_time']:.2f}s")
        
        # RAG system specific recommendations
        if rag_analysis['success_rate'] < 90:
            recommendations.append(f"RAG system success rate is low: {rag_analysis['success_rate']:.1f}%")
            recommendations.append("Consider checking embedding system health and fallback mechanisms")
        
        if rag_analysis['avg_response_time'] > 3.0:
            recommendations.append(f"RAG queries are slow: {rag_analysis['avg_response_time']:.2f}s average")
            recommendations.append("Consider optimizing vector search or adding caching")
        
        # General recommendations
        if not recommendations:
            recommendations.append("All performance metrics are within acceptable ranges")
        
        return recommendations

def print_report(report: Dict):
    """Print a formatted load test report."""
    print("\n" + "=" * 80)
    print("LOAD TEST REPORT")
    print("=" * 80)
    
    # Test Summary
    summary = report['test_summary']
    print(f"\nTest Duration: {summary['duration_seconds']:.1f} seconds")
    print(f"Total Requests: {summary['total_requests']}")
    print(f"Successful: {summary['successful_requests']} ({summary['success_rate_percent']:.1f}%)")
    print(f"Failed: {summary['failed_requests']}")
    print(f"Throughput: {summary['requests_per_second']:.2f} requests/second")
    
    # Performance Metrics
    metrics = report['performance_metrics']
    print(f"\nResponse Time Statistics:")
    print(f"  Average: {metrics['avg_response_time']:.3f}s")
    print(f"  Median:  {metrics['median_response_time']:.3f}s")
    print(f"  P95:     {metrics['p95_response_time']:.3f}s")
    print(f"  P99:     {metrics['p99_response_time']:.3f}s")
    print(f"  Min:     {metrics['min_response_time']:.3f}s")
    print(f"  Max:     {metrics['max_response_time']:.3f}s")
    
    # Endpoint Statistics
    print(f"\nEndpoint Performance:")
    for endpoint, stats in report['endpoint_statistics'].items():
        print(f"  {endpoint}:")
        print(f"    Requests: {stats['total']}")
        print(f"    Success Rate: {stats['success_rate']:.1f}%")
        print(f"    Avg Response Time: {stats['avg_response_time']:.3f}s")
        print(f"    P95 Response Time: {stats['p95_response_time']:.3f}s")
    
    # RAG System Analysis
    rag = report['rag_system_analysis']
    print(f"\nRAG System Performance:")
    print(f"  Total Queries: {rag['total_queries']}")
    print(f"  Successful: {rag['successful_queries']} ({rag['success_rate']:.1f}%)")
    print(f"  Failed: {rag['failed_queries']}")
    print(f"  Avg Response Time: {rag['avg_response_time']:.3f}s")
    
    # Error Analysis
    if report['error_analysis']:
        print(f"\nError Analysis:")
        for error, count in report['error_analysis'].items():
            print(f"  {error}: {count} occurrences")
    
    # Recommendations
    print(f"\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  • {rec}")

def main():
    """Main function to run load testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Load test the Django FAQ/RAG application')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL for testing')
    parser.add_argument('--users', type=int, default=10, help='Number of concurrent users')
    parser.add_argument('--requests', type=int, default=20, help='Requests per user')
    parser.add_argument('--ramp-up', type=int, default=30, help='Ramp-up time in seconds')
    parser.add_argument('--duration', type=int, default=300, help='Max test duration in seconds')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    parser.add_argument('--output', help='Output file for detailed results (JSON)')
    
    args = parser.parse_args()
    
    # Create configuration
    config = LoadTestConfig(
        base_url=args.url,
        concurrent_users=args.users,
        requests_per_user=args.requests,
        ramp_up_time=args.ramp_up,
        test_duration=args.duration,
        timeout=args.timeout
    )
    
    # Run load test
    tester = LoadTester(config)
    
    try:
        report = tester.run_load_test()
        
        # Print report
        print_report(report)
        
        # Save detailed results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\nDetailed results saved to: {args.output}")
        
        # Exit with appropriate code
        success_rate = report['test_summary']['success_rate_percent']
        rag_success_rate = report['rag_system_analysis']['success_rate']
        
        if success_rate >= 95 and rag_success_rate >= 90:
            print("\n🎉 Load test PASSED - All metrics within acceptable ranges")
            return 0
        else:
            print("\n❌ Load test FAILED - Some metrics below acceptable thresholds")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Load test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Load test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())