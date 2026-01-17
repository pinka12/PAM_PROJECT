"""
Real-time aggregation service for manager scores
"""
from datetime import datetime, timezone
from typing import Dict, Any, List
import statistics
from app.db import raw_responses, managers

def update_manager_aggregation(manager_name: str):
    """
    Real-time aggregation for a specific manager
    Called after each form submission
    """
    try:
        # Get ALL assessments for this manager (normalized name)
        all_assessments = list(raw_responses.find(
            {"manager_name": manager_name},
            {"processed": 1, "submittedAt": 1, "created_at": 1}
        ))
        
        if not all_assessments:
            print(f"⚠️ No assessments found for manager: {manager_name}")
            return None
        
        print(f"🔍 Aggregating {len(all_assessments)} assessments for {manager_name}")
        
        # Collect scores
        category_totals = {"trusting": 0, "tasking": 0, "tending": 0}
        category_scores_list = {"trusting": [], "tasking": [], "tending": []}
        all_timestamps = []
        
        for assessment in all_assessments:
            processed = assessment.get("processed", {})
            categories = processed.get("category_totals", {})
            timestamp = assessment.get("submittedAt") or assessment.get("created_at")
            
            if timestamp:
                all_timestamps.append(timestamp)
            
            # Sum category totals
            for category in ["trusting", "tasking", "tending"]:
                score = categories.get(category, 0)
                category_totals[category] += score
                category_scores_list[category].append(score)
        
        # Get manager info from latest assessment
        latest_assessment = all_assessments[-1]
        processed = latest_assessment.get("processed", {})
        manager_info = processed.get("manager_info", {})
        
        # Calculate statistics
        aggregated = {
            "manager_name": manager_name,
            "reporting_to": manager_info.get("reporting_to", ""),
            "raw_manager_name": manager_info.get("raw_manager_name", ""),
            "raw_reporting_to": manager_info.get("raw_reporting_to", ""),
            
            "total_assessments": len(all_assessments),
            "first_assessment": min(all_timestamps) if all_timestamps else "",
            "last_assessment": max(all_timestamps) if all_timestamps else "",
            
            # Category aggregations
            "category_totals": category_totals,
            
            "category_averages": {
                "trusting": statistics.mean(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                "tasking": statistics.mean(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                "tending": statistics.mean(category_scores_list["tending"]) if category_scores_list["tending"] else 0
            },
            
            # Score distribution
            "score_distribution": {
                "trusting": {
                    "min": min(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                    "max": max(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                    "std": statistics.stdev(category_scores_list["trusting"]) if len(category_scores_list["trusting"]) > 1 else 0
                },
                "tasking": {
                    "min": min(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                    "max": max(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                    "std": statistics.stdev(category_scores_list["tasking"]) if len(category_scores_list["tasking"]) > 1 else 0
                },
                "tending": {
                    "min": min(category_scores_list["tending"]) if category_scores_list["tending"] else 0,
                    "max": max(category_scores_list["tending"]) if category_scores_list["tending"] else 0,
                    "std": statistics.stdev(category_scores_list["tending"]) if len(category_scores_list["tending"]) > 1 else 0
                }
            },
            
            "confidence_score": min(100, len(all_assessments) * 10),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        # Check if this is a new manager
        existing_manager = managers.find_one({"manager_name": manager_name})
        is_new = existing_manager is None
        
        # Update or insert in managers collection
        result = managers.update_one(
            {"manager_name": manager_name},
            {"$set": aggregated},
            upsert=True
        )
        
        if is_new:
            # Set created_at for new managers
            managers.update_one(
                {"manager_name": manager_name},
                {"$set": {"created_at": datetime.now(timezone.utc)}}
            )
            print(f"✅ Created new manager entry: {manager_name}")
        else:
            print(f"✅ Updated manager aggregation: {manager_name}")
        
        return aggregated
        
    except Exception as e:
        print(f"❌ Error updating aggregation for {manager_name}: {e}")
        import traceback
        traceback.print_exc()
        raise

def migrate_existing_data():
    """
    Process all existing form responses to create initial manager entries
    """
    try:
        print("=" * 60)
        print("🔄 Starting migration of existing form responses...")
        print("=" * 60)
        
        # First, ensure all existing responses have normalized names
        print("📝 Normalizing names in existing responses...")
        
        all_responses = list(raw_responses.find({}))
        print(f"Found {len(all_responses)} responses in database")
        
        if len(all_responses) == 0:
            print("⚠️  No form responses found in database!")
            return {"success": False, "error": "No form responses found"}
        
        normalized_count = 0
        
        for response in all_responses:
            answers = response.get("raw_answers", {})
            manager_name = ""
            reporting_to = ""
            
            # Extract names from raw answers
            for full_question, answer_list in answers.items():
                if not answer_list:
                    continue
                
                answer = answer_list[0].strip()
                
                if "manager's full name" in full_question.lower():
                    from app.processor import normalize_name
                    manager_name = normalize_name(answer)
                
                elif "manager report to" in full_question.lower():
                    from app.processor import normalize_name
                    reporting_to = normalize_name(answer)
            
            # Update the response with normalized names
            if manager_name:
                raw_responses.update_one(
                    {"_id": response["_id"]},
                    {"$set": {
                        "manager_name": manager_name,
                        "reporting_to": reporting_to
                    }}
                )
                normalized_count += 1
        
        print(f"✅ Normalized {normalized_count} existing responses")
        
        # Get all unique managers from existing responses
        pipeline = [
            {"$group": {"_id": "$manager_name"}},
            {"$match": {"_id": {"$ne": None, "$ne": ""}}}
        ]
        
        unique_managers = list(raw_responses.aggregate(pipeline))
        
        print(f"📊 Found {len(unique_managers)} unique managers in existing data")
        
        if len(unique_managers) == 0:
            print("⚠️  No unique managers found after normalization!")
            return {"success": False, "error": "No unique managers found"}
        
        created_count = 0
        updated_count = 0
        
        for manager in unique_managers:
            manager_name = manager["_id"]
            if manager_name:
                print(f"Processing manager: {manager_name}")
                result = update_manager_aggregation(manager_name)
                if result:
                    # Check if this was a new creation
                    manager_doc = managers.find_one({"manager_name": manager_name})
                    if manager_doc and "created_at" in manager_doc:
                        created_count += 1
                        print(f"  ✓ Created: {manager_name}")
                    else:
                        updated_count += 1
                        print(f"  ✓ Updated: {manager_name}")
        
        print("=" * 60)
        print("✅ Migration complete!")
        print(f"   Created: {created_count} new manager entries")
        print(f"   Updated: {updated_count} existing manager entries")
        
        # Verify
        total_managers = managers.count_documents({})
        print(f"   Total managers in collection: {total_managers}")
        
        # Show sample of managers
        sample_managers = list(managers.find({}, {"manager_name": 1, "total_assessments": 1}).limit(5))
        print(f"   Sample managers:")
        for mgr in sample_managers:
            print(f"     - {mgr['manager_name']}: {mgr.get('total_assessments', 0)} assessments")
        print("=" * 60)
        
        return {
            "success": True,
            "created": created_count,
            "updated": updated_count,
            "total": total_managers
        }
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

from typing import Dict, List, Optional
from collections import defaultdict

# ==================== HIERARCHY FUNCTIONS ====================
from typing import Dict, List, Optional
from collections import defaultdict
import math

async def get_manager_hierarchy(manager_id: Optional[str] = None, db=None):
    """
    Build complete organizational hierarchy tree
    
    Args:
        manager_id: Optional starting manager ID. If None, builds full company tree
        db: MongoDB database instance (will use managers collection from db module)
    
    Returns:
        dict: Complete hierarchical tree with metrics
    """
    try:
        # Import here to avoid circular imports
        from app.db import managers
        
        # Get all managers from database
        all_managers_cursor = managers.find({})
        all_managers = await all_managers_cursor.to_list(length=1000)
        
        if not all_managers:
            return {"error": "No managers found"}
        
        # Convert MongoDB documents to dict and create lookup
        manager_dict = {}
        reporting_map = defaultdict(list)  # manager_name -> list of direct reports
        
        for manager in all_managers:
            # Convert ObjectId to string for JSON serialization
            manager["_id"] = str(manager["_id"])
            
            # Store in lookup dict
            manager_name = manager.get("manager_name", "")
            manager_dict[manager_name] = manager
            
            # Build reporting relationship
            reports_to = manager.get("reporting_to", "")
            if reports_to:  # Has a manager
                reporting_map[reports_to].append(manager_name)
        
        # Find root(s) - managers who don't report to anyone
        roots = []
        all_reporting_names = set(reporting_map.keys())
        all_manager_names = set(manager_dict.keys())
        
        for manager_name in all_manager_names:
            if manager_name not in all_reporting_names:
                # This manager might be a leaf or root
                # Check if they have reports
                if manager_name in reporting_map and reporting_map[manager_name]:
                    roots.append(manager_name)
                elif not manager_dict[manager_name].get("reporting_to"):
                    # No reporting_to field, treat as root
                    roots.append(manager_name)
        
        # If we have a specific start manager, use that as root
        if manager_id:
            start_id = manager_id
            if start_id in manager_dict:
                # Build subtree from this manager
                hierarchy = build_subtree(start_id, manager_dict, reporting_map)
                return {
                    "tree": hierarchy,
                    "type": "subtree",
                    "root_manager": manager_dict[start_id],
                    "total_managers": count_nodes(hierarchy),
                    "statistics": calculate_tree_statistics(hierarchy)
                }
            else:
                # Manager not found, return full hierarchy
                pass
        
        # Build full organizational tree
        full_hierarchy = []
        for root_id in roots:
            if root_id in manager_dict:  # Check if root exists
                root_tree = build_subtree(root_id, manager_dict, reporting_map)
                if root_tree:
                    full_hierarchy.append(root_tree)
        
        # Calculate organizational statistics
        org_stats = calculate_organization_statistics(full_hierarchy)
        
        return {
            "hierarchy": full_hierarchy,
            "type": "full_organization",
            "root_count": len(roots),
            "total_managers": len(all_managers),
            "statistics": org_stats,
            "reporting_structure": build_reporting_structure(manager_dict, reporting_map)
        }
        
    except Exception as e:
        print(f"Error in get_manager_hierarchy: {str(e)}")
        return {"error": f"Error building hierarchy: {str(e)}"}

def build_subtree(manager_name: str, manager_dict: Dict, reporting_map: Dict) -> Dict:
    """
    Recursively build subtree from a manager
    """
    if manager_name not in manager_dict:
        return None
    
    manager = manager_dict[manager_name].copy()
    
    # Get direct reports
    direct_reports = []
    if manager_name in reporting_map:
        for report_name in reporting_map[manager_name]:
            child_tree = build_subtree(report_name, manager_dict, reporting_map)
            if child_tree:
                direct_reports.append(child_tree)
    
    # Add hierarchy information
    manager["direct_reports_count"] = len(direct_reports)
    manager["total_reports"] = count_total_reports(direct_reports)
    
    # Calculate hierarchy level (distance from root)
    manager["hierarchy_level"] = 0
    current = manager
    while current.get("reporting_to"):
        manager["hierarchy_level"] += 1
        # Need to find parent
        break
    
    return {
        "manager": manager,
        "direct_reports": direct_reports
    }

def count_nodes(tree: Dict) -> int:
    """Count total nodes in tree"""
    if not tree:
        return 0
    
    count = 1  # Current node
    if "direct_reports" in tree:
        for child in tree["direct_reports"]:
            count += count_nodes(child)
    return count

def count_total_reports(direct_reports: List) -> int:
    """Count total reports (including indirect)"""
    total = len(direct_reports)
    for report in direct_reports:
        total += count_total_reports(report.get("direct_reports", []))
    return total

def calculate_tree_statistics(tree: Dict) -> Dict:
    """Calculate statistics for a single tree"""
    stats = {
        "total_nodes": 0,
        "trusting_avg": 0,
        "tasking_avg": 0,
        "tending_avg": 0,
        "max_depth": 0
    }
    
    def traverse(tree, depth=0):
        if not tree:
            return
        
        manager = tree.get("manager", {})
        stats["total_nodes"] += 1
        
        # Accumulate scores
        category_avgs = manager.get("category_averages", {})
        stats["trusting_avg"] += category_avgs.get("trusting", 0)
        stats["tasking_avg"] += category_avgs.get("tasking", 0)
        stats["tending_avg"] += category_avgs.get("tending", 0)
        
        # Track depth
        stats["max_depth"] = max(stats["max_depth"], depth)
        
        # Recurse for children
        for child in tree.get("direct_reports", []):
            traverse(child, depth + 1)
    
    traverse(tree)
    
    # Calculate averages
    if stats["total_nodes"] > 0:
        stats["trusting_avg"] /= stats["total_nodes"]
        stats["tasking_avg"] /= stats["total_nodes"]
        stats["tending_avg"] /= stats["total_nodes"]
    
    return stats

def calculate_organization_statistics(hierarchy_trees: List) -> Dict:
    """Calculate organizational-level statistics"""
    stats = {
        "total_managers": 0,
        "trusting_avg": 0,
        "tasking_avg": 0,
        "tending_avg": 0,
        "confidence_avg": 0,
        "max_depth": 0,
        "avg_span_of_control": 0
    }
    
    def traverse_and_collect(tree, depth=0):
        if not tree:
            return
        
        manager = tree.get("manager", {})
        stats["total_managers"] += 1
        
        # Accumulate scores
        category_avgs = manager.get("category_averages", {})
        stats["trusting_avg"] += category_avgs.get("trusting", 0)
        stats["tasking_avg"] += category_avgs.get("tasking", 0)
        stats["tending_avg"] += category_avgs.get("tending", 0)
        stats["confidence_avg"] += manager.get("confidence_score", 0)
        
        # Track depth
        stats["max_depth"] = max(stats["max_depth"], depth)
        
        # Span of control
        direct_reports = len(tree.get("direct_reports", []))
        stats["avg_span_of_control"] += direct_reports
        
        # Recurse for children
        for child in tree.get("direct_reports", []):
            traverse_and_collect(child, depth + 1)
    
    for tree in hierarchy_trees:
        traverse_and_collect(tree)
    
    # Calculate averages
    if stats["total_managers"] > 0:
        stats["trusting_avg"] /= stats["total_managers"]
        stats["tasking_avg"] /= stats["total_managers"]
        stats["tending_avg"] /= stats["total_managers"]
        stats["confidence_avg"] /= stats["total_managers"]
        stats["avg_span_of_control"] /= stats["total_managers"]
    
    return stats

def build_reporting_structure(manager_dict: Dict, reporting_map: Dict) -> List:
    """Build flat reporting structure for easy frontend consumption"""
    structure = []
    
    for manager_name, reports in reporting_map.items():
        manager_info = {
            "manager": manager_name,
            "manager_data": manager_dict.get(manager_name, {}),
            "direct_reports": [
                {
                    "name": report_name,
                    "data": manager_dict.get(report_name, {}),
                    "trusting_avg": manager_dict.get(report_name, {}).get("category_averages", {}).get("trusting", 0),
                    "tasking_avg": manager_dict.get(report_name, {}).get("category_averages", {}).get("tasking", 0),
                    "tending_avg": manager_dict.get(report_name, {}).get("category_averages", {}).get("tending", 0)
                }
                for report_name in reports if report_name in manager_dict
            ],
            "report_count": len(reports)
        }
        structure.append(manager_info)
    
    return structure
# Add this to make the file runnable directly
if __name__ == "__main__":
    result = migrate_existing_data()
    if result.get("success"):
        print("\n🎉 Migration successful!")
    else:
        print(f"\n❌ Migration failed: {result.get('error')}")