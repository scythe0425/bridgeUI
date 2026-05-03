import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bridge_ui/main.dart';

void main() {
  testWidgets('트리거 버튼이 렌더링된다', (WidgetTester tester) async {
    await tester.pumpWidget(const BridgeUIApp());

    expect(find.byIcon(Icons.search), findsOneWidget);
    expect(find.text('버튼을 눌러 화면을 분석하세요'), findsOneWidget);
  });
}
