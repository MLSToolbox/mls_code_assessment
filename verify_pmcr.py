import os
import sys
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from analyzers.factory import AnalyzerFactory
from core.analysis_context import AnalysisContext

def verify_pmcr():
    # Mock session and path
    session_id = "test_session"
    local_path = os.getcwd()
    
    # Create context
    context = AnalysisContext(session_id, local_path)
    
    # Create analyzer
    try:
        analyzer = AnalyzerFactory.create_analyzer("pmcr", session_id, local_path, context)
        print("PMCR Analyzer created successfully.")
    except Exception as e:
        print(f"Failed to create analyzer: {e}")
        return

    # Run analysis
    try:
        result = analyzer.analyze()
        print("\nAnalysis completed.")
        print(f"Score: {result.score}")
        
        # Print summary
        summary = result.details['summary']
        print("\nSummary:")
        print(json.dumps(summary, indent=2))
        
        # Print package details
        print("\nPackage Details:")
        for pkg, data in result.details['packages'].items():
            if data['pmcr'] is not None:
                print(f"\nPackage: {pkg}")
                print(f"  PMCR: {data['pmcr']}")
                print(f"  Modules: {data['n_modules']}")
                print(f"  Connected Pairs: {data['n_connected_pairs']} / {data['n_possible_pairs']}")
                print(f"  Connected Components: {data['connected_components']}")
                if data['direct_connections']:
                    print("  Sample Connections:")
                    for conn in data['direct_connections'][:3]:
                        print(f"    - {conn['module_a']} <-> {conn['module_b']}: {conn['reasons']}")

    except Exception as e:
        print(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_pmcr()
