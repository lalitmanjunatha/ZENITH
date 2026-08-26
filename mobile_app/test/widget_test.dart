import 'package:flutter_test/flutter_test.dart';

import 'package:zenith_mobile/main.dart';

void main() {
  testWidgets('App boots to home shell', (WidgetTester tester) async {
    await tester.pumpWidget(ZenithMobileApp());
    await tester.pump();
    expect(find.byType(ZenithMobileApp), findsOneWidget);
  });
}
